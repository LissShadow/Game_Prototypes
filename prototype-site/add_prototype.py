"""Register a standalone HTML prototype, its cover and RU/EN metadata. No npm required."""
from pathlib import Path
from html.parser import HTMLParser
import argparse,json,re,shutil,subprocess,sys
from catalog_schema import load_catalog,validate_catalog,relative_path
SOURCE=Path(__file__).resolve().parent
ROOT=SOURCE.parent

class Resources(HTMLParser):
    def __init__(self):super().__init__();self.links=set()
    def handle_starttag(self,tag,attrs):
        if tag not in {'script','img','link','iframe','audio','video','source'}:return
        for key,value in attrs:
            if key in {'src','href'} and value and not value.startswith(('data:','#','blob:','about:')):self.links.add(value)

def html_file(path):
    path=Path(path).resolve()
    if not path.is_file() or path.suffix.lower() not in {'.html','.htm'}:raise ValueError(f'HTML file not found: {path}')
    with path.open('rb') as stream:header=stream.read(4096)
    if header.startswith(b'version https://git-lfs.github.com/spec/v1'):raise ValueError('An LFS pointer is not an HTML game')
    if not header.strip():raise ValueError('The HTML file is empty')
    if path.stat().st_size>=100*1048576:raise ValueError('HTML is too large for regular Git (100 MiB limit); optimize the prototype first')
    return path

def inside(file):
    parts=relative_path(file,'game file');path=(ROOT/Path(*parts.parts)).resolve()
    if not path.is_relative_to(ROOT):raise ValueError('Game path leaves the repository')
    return html_file(path)

def register(args):
    data=load_catalog(SOURCE/'prototypes.json')
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',args.id):raise ValueError('Use a lowercase ASCII id, e.g. another-game')
    if any(item['id']==args.id for item in data):raise ValueError(f'This id already exists: {args.id}')
    languages=[value.strip() for value in args.languages.split(',')]
    if not languages or not all(value in {'ru','en'} for value in languages):raise ValueError('--languages must be ru, en or ru,en')
    cover=Path(args.cover).resolve()
    if not cover.is_file() or cover.suffix.lower() not in {'.webp','.png','.jpg','.jpeg'}:raise ValueError('Cover must be an existing WebP, PNG or JPEG file')
    cover_relative=f'assets/{args.id}-cover{cover.suffix.lower()}'
    cover_target=SOURCE/cover_relative
    if cover_target.exists():raise ValueError(f'Cover already exists; nothing overwritten: {cover_target}')
    game_folder=ROOT/'games'/args.id
    if args.html:
        source_html=html_file(args.html)
        if game_folder.exists():raise ValueError(f'Game folder already exists; nothing overwritten: {game_folder}')
        game_relative=f'games/{args.id}/index.html'
    else:
        inside(args.file);source_html=None;game_relative=args.file
    item={'id':args.id,'title':{'ru':args.title_ru,'en':args.title_en},'category':{'ru':args.category_ru,'en':args.category_en},'description':{'ru':args.description_ru,'en':args.description_en},'image':cover_relative,'file':game_relative,'tags':{'ru':[s.strip() for s in args.tags_ru.split(',') if s.strip()],'en':[s.strip() for s in args.tags_en.split(',') if s.strip()]},'languages':list(dict.fromkeys(languages))}
    if args.version:item['version']=args.version
    versions={lang:value for lang,value in [('ru',args.file_ru),('en',args.file_en)] if value}
    for file in versions.values():inside(file)
    if versions:item['files']=versions
    validate_catalog([*data,item])
    if args.dry_run:
        print(json.dumps(item,ensure_ascii=False,indent=2));print('Dry run: no files were changed.');return item
    manifest=SOURCE/'prototypes.json';before=manifest.read_bytes();copied=[]
    try:
        if source_html:
            game_folder.mkdir(parents=True);target=game_folder/'index.html';shutil.copy2(source_html,target);copied.append(target)
        shutil.copy2(cover,cover_target);copied.append(cover_target)
        manifest.write_text(json.dumps([*data,item],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        subprocess.run([sys.executable,str(SOURCE/'build.py')],check=True)
    except Exception:
        manifest.write_bytes(before)
        for path in copied:path.unlink(missing_ok=True)
        if source_html and game_folder.exists() and not any(game_folder.iterdir()):game_folder.rmdir()
        raise
    print(f'Added {args.id}: {game_relative}. Commit the HTML, cover, manifest and rebuilt index.html.')
    print('The site language and the game language are independent. Use files.ru/files.en only for separate HTML builds.')
    if source_html:
        probe=Resources()
        try:probe.feed(source_html.read_text(encoding='utf-8-sig'))
        except (UnicodeError,ValueError):print('Warning: could not inspect external resources; check that the game is self-contained.')
        if probe.links:print('Warning: non-embedded resources detected; standalone import does not copy them: '+', '.join(sorted(probe.links)[:5]))
    return item

def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--id',required=True)
    group=p.add_mutually_exclusive_group(required=True);group.add_argument('--html',help='Standalone HTML to copy into games/ID/index.html');group.add_argument('--file',help='Already existing HTML path relative to repository root; do not copy')
    p.add_argument('--cover',required=True);p.add_argument('--title-ru',required=True);p.add_argument('--title-en',required=True)
    p.add_argument('--description-ru',default='');p.add_argument('--description-en',default='')
    p.add_argument('--category-ru',default='Игровой прототип');p.add_argument('--category-en',default='Game prototype')
    p.add_argument('--tags-ru',default='');p.add_argument('--tags-en',default='');p.add_argument('--version',default='')
    p.add_argument('--languages',required=True,help='Languages supported by the game: ru, en or ru,en')
    p.add_argument('--file-ru',help='Optional existing Russian HTML build');p.add_argument('--file-en',help='Optional existing English HTML build')
    p.add_argument('--dry-run',action='store_true');return p

if __name__=='__main__':
    try:register(parser().parse_args())
    except (ValueError,OSError,KeyError,subprocess.CalledProcessError) as error:sys.exit(f'Prototype was not added: {error}')
