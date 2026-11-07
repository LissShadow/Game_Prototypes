"""Shared, dependency-free validation for the bilingual prototype manifest."""
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit, unquote
import json,re
LANGUAGES={'ru','en'}

def relative_path(value,label):
    if not isinstance(value,str) or not value.strip():raise ValueError(f'{label}: expected a relative path')
    url=urlsplit(value);path=PurePosixPath(unquote(url.path))
    if url.scheme or url.netloc or url.query or url.fragment or path.is_absolute() or '..' in path.parts or '\\' in value or not path.parts:
        raise ValueError(f'{label}: use a local relative path without .., queries or fragments')
    if any(part.startswith('.') for part in path.parts):raise ValueError(f'{label}: hidden paths are not allowed')
    return path

def localized(value,label,required=False):
    if isinstance(value,str):
        if required and not value.strip():raise ValueError(f'{label}: empty text')
        return
    if not isinstance(value,dict) or set(value)!=LANGUAGES:raise ValueError(f'{label}: supply both ru and en text, or a shared string')
    for lang,text in value.items():
        if not isinstance(text,str) or (required and not text.strip()):raise ValueError(f'{label}.{lang}: expected text')

def validate_catalog(data):
    if not isinstance(data,list):raise ValueError('Catalog must be a JSON array')
    seen=set()
    for i,item in enumerate(data):
        label=f'Prototype #{i+1}'
        if not isinstance(item,dict):raise ValueError(f'{label}: expected an object')
        identity=item.get('id','')
        if not isinstance(identity,str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',identity):raise ValueError(f'{label}: id must be a lowercase ASCII slug')
        if identity in seen:raise ValueError(f'Duplicate prototype id: {identity}')
        seen.add(identity);localized(item.get('title'),identity+'.title',True)
        relative_path(item.get('file'),identity+'.file')
        if PurePosixPath(item['file']).suffix.lower() not in {'.html','.htm'}:raise ValueError(f'{identity}: file must be HTML')
        relative_path(item.get('image'),identity+'.image')
        for field in ['category','description']:
            if field in item:localized(item[field],identity+'.'+field)
        if 'version' in item and not isinstance(item['version'],str):raise ValueError(f'{identity}: version must be text')
        if 'tags' in item:
            tags=item['tags']
            arrays=tags.values() if isinstance(tags,dict) and set(tags)==LANGUAGES else [tags]
            for array in arrays:
                if not isinstance(array,list) or not all(isinstance(t,str) for t in array):raise ValueError(f'{identity}: tags must be an array or ru/en arrays')
        if 'languages' in item and (not isinstance(item['languages'],list) or not item['languages'] or not all(isinstance(lang,str) for lang in item['languages']) or not set(item['languages'])<=LANGUAGES):raise ValueError(f'{identity}: languages must list ru and/or en')
        if 'files' in item:
            if not isinstance(item['files'],dict) or not item['files'] or not set(item['files'])<=LANGUAGES:raise ValueError(f'{identity}: files must map ru and/or en to HTML paths')
            for lang,file in item['files'].items():
                relative_path(file,identity+'.files.'+lang)
                if PurePosixPath(file).suffix.lower() not in {'.html','.htm'}:raise ValueError(f'{identity}: localized entry point must be HTML')
    return data

def load_catalog(path):
    return validate_catalog(json.loads(Path(path).read_text(encoding='utf-8')))

def entry_files(item):
    return list(dict.fromkeys([item['file'],*item.get('files',{}).values()]))
