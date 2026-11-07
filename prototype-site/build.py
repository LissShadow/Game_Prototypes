"""Build the bilingual, single-file catalog beside the standalone game files."""
from pathlib import Path
import base64,json,mimetypes,sys
from catalog_schema import load_catalog
R=Path(__file__).resolve().parent

def build():
    catalog=load_catalog(R/'prototypes.json')
    for item in catalog:
        image=(R/item['image']).resolve()
        if not image.is_relative_to(R) or not image.is_file():raise ValueError(f'Cover not found inside site sources: {item["image"]}')
        mime=mimetypes.guess_type(str(image))[0]
        if mime not in {'image/webp','image/png','image/jpeg','image/svg+xml'}:raise ValueError(f'Unsupported cover format: {image.name}')
        item['image']='data:'+mime+';base64,'+base64.b64encode(image.read_bytes()).decode()
    locales=json.loads((R/'locales.json').read_text(encoding='utf-8'))
    if set(locales)!={'ru','en'} or set(locales['ru'])!=set(locales['en']):raise ValueError('Site locales must have matching ru/en keys')
    if not all(isinstance(value,str) for dictionary in locales.values() for value in dictionary.values()):raise ValueError('Site translations must be strings')
    font='data:font/ttf;base64,'+base64.b64encode((R/'assets/Manrope.ttf').read_bytes()).decode()
    style=(R/'style.css').read_text(encoding='utf-8').replace('__FONT__',font)
    encode=lambda value:json.dumps(value,ensure_ascii=False).replace('<','\\u003c')
    html=(R/'index.template.html').read_text(encoding='utf-8').replace('/*__STYLE__*/',style).replace('/*__SCRIPT__*/',(R/'app.js').read_text(encoding='utf-8')).replace('/*__CATALOG__*/',encode(catalog)).replace('/*__LOCALES__*/',encode(locales))
    html=html.replace('<html lang="ru">','<!-- Embedded font: Manrope. '+(R/'assets/Manrope-OFL.txt').read_text(encoding='utf-8')+' -->\n<html lang="ru">',1)
    if any(token in html for token in ['/*__STYLE__*/','/*__SCRIPT__*/','/*__CATALOG__*/','/*__LOCALES__*/','__FONT__']):raise ValueError('Unresolved template tokens')
    output=R.parent/'index.html';output.write_text(html,encoding='utf-8');print(f'Built {output}: {output.stat().st_size/1024:.1f} KiB')
    return output

if __name__=='__main__':
    try:build()
    except (ValueError,OSError,KeyError) as error:sys.exit(f'Catalog build failed: {error}')
