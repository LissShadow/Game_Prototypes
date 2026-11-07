"""Test the exact Pages artifact, including serving from a project-repository subpath."""
from pathlib import Path
from tempfile import TemporaryDirectory
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.request import urlopen
from urllib.parse import urljoin
import importlib.util, json, shutil, threading, subprocess

SOURCE=Path(__file__).resolve().parents[1]
ROOT=SOURCE.parent
spec=importlib.util.spec_from_file_location('pages_builder',SOURCE/'prepare_pages.py')
pages=importlib.util.module_from_spec(spec);spec.loader.exec_module(pages)

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args): pass

with TemporaryDirectory(prefix='olga-pages-test-') as tmp:
    tmp=Path(tmp)
    # Build from a separate fixture so the working catalog is never edited.
    fixture=tmp/'repository';fixture.mkdir()
    shutil.copytree(SOURCE,fixture/'prototype-site',ignore=shutil.ignore_patterns('node_modules','__pycache__'))
    shutil.copy2(ROOT/'Book-Tamer.html',fixture/'Book-Tamer.html')
    game=fixture/'future-game';(game/'assets').mkdir(parents=True)
    (game/'index.html').write_text('<!doctype html><title>Future fixture</title><link rel="stylesheet" href="assets/style.css">')
    (game/'assets/style.css').write_text('body{background:#123}')
    (game/'.env').write_text('SHOULD_NOT_BE_PUBLISHED=1')
    (game/'node_modules').mkdir();(game/'node_modules/unused.js').write_text('unused')
    manifest=fixture/'prototype-site/prototypes.json';data=json.loads(manifest.read_text(encoding='utf-8'))
    data.append({'id':'fixture','title':'Future fixture','file':'future-game/index.html','image':'assets/book-tamer-cover.webp'})
    manifest.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    pages.ROOT=fixture;pages.SOURCE=fixture/'prototype-site'
    public_parent=tmp/'public';output=public_parent/'project-name'
    pages.stage(output)
    assert {p.name for p in output.iterdir()}=={'index.html','Book-Tamer.html','future-game','.nojekyll'}
    assert (output/'Book-Tamer.html').read_bytes()==(ROOT/'Book-Tamer.html').read_bytes()
    assert (output/'future-game/assets/style.css').is_file()
    assert not (output/'future-game/.env').exists()
    assert not (output/'future-game/node_modules').exists()
    assert 'Future fixture' in (output/'index.html').read_text(encoding='utf-8')
    for invalid in ['../Book-Tamer.html','/Book-Tamer.html','https://example.com/game.html','%2e%2e/Book-Tamer.html','prototype-site/index.template.html','missing.html']:
        try:pages.game_path(invalid)
        except ValueError:pass
        else:raise AssertionError('Unsafe/missing path accepted: '+invalid)
    try:pages.stage(output)
    except ValueError:pass
    else:raise AssertionError('Nonempty destination accepted')
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(public_parent)))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        base=f'http://127.0.0.1:{server.server_port}/project-name/'
        for entry in ['','Book-Tamer.html','future-game/index.html','future-game/assets/style.css']:
            with urlopen(urljoin(base,entry)) as response:
                assert response.status==200
                response.read()
        assert urljoin(base,'Book-Tamer.html').endswith('/project-name/Book-Tamer.html')
    finally:server.shutdown();server.server_close();thread.join()
    # Check .gitignore without creating .git or duplicating git objects in the real workspace.
    git=tmp/'ignore-check';git.mkdir();shutil.copy2(ROOT/'.gitignore',git/'.gitignore')
    subprocess.run(['git','init','-q',str(git)],check=True)
    for name in ['heartbound-word/asset.webp','node_modules/x.js','.env','.cache/x','_site/index.html']:
        assert subprocess.run(['git','-C',str(git),'check-ignore','--no-index','-q',name]).returncode==0,name
    for name in ['index.html','Book-Tamer.html','.github/workflows/pages.yml','prototype-site/app.js','future-game/index.html']:
        assert subprocess.run(['git','-C',str(git),'check-ignore','--no-index','-q',name]).returncode==1,name
print('PASS: clean Pages artifact; unchanged standalone game; future game + relative resources; no sources/secrets/dependencies; root-relative project hosting URLs; safe paths; non-destructive output; gitignore.')
