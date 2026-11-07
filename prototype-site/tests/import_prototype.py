"""Exercise standalone HTML registration, localized entry points, validation and Pages staging."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json,shutil,subprocess,sys
SOURCE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SOURCE))
from catalog_schema import validate_catalog
with TemporaryDirectory(prefix='prototype-import-test-') as tmp:
    tmp=Path(tmp);root=tmp/'repo';root.mkdir();source=root/'prototype-site'
    shutil.copytree(SOURCE,source,ignore=shutil.ignore_patterns('node_modules','__pycache__'))
    manifest=source/'prototypes.json';manifest.write_text('[]',encoding='utf-8')
    incoming=tmp/'incoming.html';incoming.write_text('<!doctype html><meta charset="utf-8"><title>Standalone</title><p>Test</p>',encoding='utf-8')
    cover=tmp/'cover.webp';shutil.copy2(SOURCE/'assets/book-tamer-cover.webp',cover)
    command=[sys.executable,str(source/'add_prototype.py'),'--id','test-game','--html',str(incoming),'--cover',str(cover),'--title-ru','Тестовая игра','--title-en','Test game','--description-ru','Русское описание.','--description-en','English description.','--languages','ru,en','--version','0.1']
    subprocess.run([*command,'--dry-run'],check=True,stdout=subprocess.PIPE)
    assert manifest.read_text()=='[]';assert not (root/'games/test-game').exists()
    subprocess.run(command,check=True,stdout=subprocess.PIPE)
    assert (root/'games/test-game/index.html').read_bytes()==incoming.read_bytes()
    data=json.loads(manifest.read_text(encoding='utf-8'));assert len(data)==1;assert data[0]['title']['en']=='Test game';assert (source/data[0]['image']).is_file()
    before=manifest.read_bytes();duplicate=subprocess.run(command,capture_output=True);assert duplicate.returncode!=0;assert manifest.read_bytes()==before
    bundle=root/'games/test-game'
    (bundle/'ru.html').write_text('<!doctype html><title>RU</title>');(bundle/'en.html').write_text('<!doctype html><title>EN</title>')
    data[0]['files']={'ru':'games/test-game/ru.html','en':'games/test-game/en.html'}
    manifest.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    unlisted=root/'games/unlisted';unlisted.mkdir();(unlisted/'index.html').write_text('<title>Not published</title>')
    (bundle/'.env').write_text('NOT_PUBLIC=1')
    output=tmp/'public'
    subprocess.run([sys.executable,str(source/'prepare_pages.py'),'--output',str(output)],check=True,stdout=subprocess.PIPE)
    for filename in ['index.html','ru.html','en.html']:assert (output/'games/test-game'/filename).is_file()
    assert not (output/'games/unlisted').exists();assert not (output/'games/test-game/.env').exists()
    assert not (output/'prototype-site').exists()
    # A build error rolls back the registration rather than leaving partial manifest/files.
    before=manifest.read_bytes();locales=json.loads((source/'locales.json').read_text(encoding='utf-8'));locales['en'].pop('back');(source/'locales.json').write_text(json.dumps(locales),encoding='utf-8')
    broken=[s if s!='test-game' else 'broken-game' for s in command]
    failed=subprocess.run(broken,capture_output=True);assert failed.returncode!=0;assert manifest.read_bytes()==before
    assert not (root/'games/broken-game').exists();assert not (source/'assets/broken-game-cover.webp').exists()
    for mutation in [dict(data[0],id='bad id'),dict(data[0],title={'ru':'Без перевода'}),dict(data[0],file='../escape.html'),dict(data[0],files={'en':'https://example.com/game.html'})]:
        try:validate_catalog([mutation])
        except ValueError:pass
        else:raise AssertionError('Invalid manifest accepted')
print('PASS: dry run; exact standalone copy; bilingual metadata; duplicate guard; optional RU/EN builds; only registered game bundles deployed; no secret/source deployment; failed import rollback; invalid schema/path detection.')
