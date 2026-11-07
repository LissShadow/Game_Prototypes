"""Build and stage a GitHub Pages site, without publishing source files or duplicating games in git."""
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit, unquote
import argparse, json, shutil, subprocess, sys
SOURCE = Path(__file__).resolve().parent
ROOT = SOURCE.parent
sys.path.insert(0,str(SOURCE))
from catalog_schema import load_catalog, entry_files


def game_path(value):
    if not isinstance(value, str) or not value:
        raise ValueError('Game file must be a non-empty relative path')
    url = urlsplit(value)
    decoded = unquote(url.path)
    parts = PurePosixPath(decoded)
    if url.scheme or url.netloc or url.query or url.fragment or '\\' in decoded or parts.is_absolute() or '..' in parts.parts:
        raise ValueError(f'Only local relative game paths are allowed: {value}')
    if not parts.parts or parts.parts[0].startswith('.') or parts.parts[0] in {'prototype-site', 'heartbound-word', 'index.html', 'README.md'}:
        raise ValueError(f'Reserved deployment path: {value}')
    if any((ROOT / Path(*parts.parts[:i])).is_symlink() for i in range(1, len(parts.parts) + 1)):
        raise ValueError(f'Symbolic links are not supported: {value}')
    if parts.parts[0]=='games' and len(parts.parts)<3:
        raise ValueError('Use games/ID/index.html, not a shared games/index.html')
    target = (ROOT / Path(*parts.parts)).resolve()
    if not target.is_relative_to(ROOT) or target.is_symlink() or not target.is_file():
        raise ValueError(f'Game HTML not found inside repository: {value}')
    if target.suffix.lower() not in {'.html', '.htm'}:
        raise ValueError(f'Game entry point must be HTML: {value}')
    with target.open('rb') as stream:
        header = stream.read(128)
    if header.startswith(b'version https://git-lfs.github.com/spec/v1'):
        raise ValueError(f'Game is an LFS pointer, not HTML: {value}. Store the standalone game in regular Git.')
    if not header.strip():
        raise ValueError(f'Empty game HTML: {value}')
    return target, parts


def stage(output):
    output = Path(output).resolve()
    # Never replace any existing files. Run with a fresh output directory.
    if output == ROOT or ROOT.is_relative_to(output) or output == SOURCE or SOURCE.is_relative_to(output):
        raise ValueError('Output must not contain the repository or its source folder')
    if output.exists() and any(output.iterdir()):
        raise ValueError(f'Output directory must be empty: {output}')
    catalog = load_catalog(SOURCE / 'prototypes.json')
    files = list(dict.fromkeys(file for item in catalog for file in entry_files(item)))
    games = [game_path(file) for file in files]
    # A game folder is copied with its local resources; root-level HTML is standalone.
    folders = {Path(*parts.parts[:2]) if parts.parts[0]=='games' and len(parts.parts)>=3 else Path(parts.parts[0]) for _, parts in games if len(parts.parts)>1}
    for folder in folders:
        source_folder = ROOT / folder
        if any(p.is_symlink() for p in source_folder.rglob('*')):
            raise ValueError(f'Symbolic links are not supported in game folders: {folder}')
        if (source_folder / '.git').exists():
            raise ValueError('Do not publish a nested git repository as a game folder')
        resolved = source_folder.resolve()
        if output == resolved or output.is_relative_to(resolved):
            raise ValueError('Output must not be inside a game folder')
    subprocess.run([sys.executable, str(SOURCE / 'build.py')], check=True)
    output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / 'index.html', output / 'index.html')
    for folder in sorted(folders):
        (output / folder).parent.mkdir(parents=True,exist_ok=True)
        shutil.copytree(ROOT / folder, output / folder,
                        ignore=shutil.ignore_patterns('node_modules', '.git', '.env', '.env.*', '__pycache__', '.DS_Store', '*.log'))
    for target, parts in games:
        if len(parts.parts) == 1:
            shutil.copy2(target, output / parts.name)
    (output / '.nojekyll').write_text('', encoding='utf-8')
    for _, parts in games:
        if not (output / Path(*parts.parts)).is_file():
            raise ValueError(f'Missing deployed game: {parts}')
    size = sum(p.stat().st_size for p in output.rglob('*') if p.is_file())
    print(f'GitHub Pages ready: {output} | {len(catalog)} prototype(s), {len(games)} HTML entry point(s) | {size / 1048576:.2f} MiB')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='An empty deployment directory, e.g. /tmp/pages-site')
    args = parser.parse_args()
    try:
        stage(args.output)
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as error:
        parser.exit(1, f'Pages build failed: {error}\n')
