"""Persistent, immutable bundle copies. Never cache a game's object IDs or routes."""
import hashlib
import json
from pathlib import Path
import re
import uuid
from app_storage import data_root

FORMAT = 1  # Bump when CAB rewriting or expected-asset metadata changes.
FIELDS = ('name', 'kind', 'objects', 'original_bundle_name', 'clone_bundle_name')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def atomic_json(path, value):
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True), encoding='utf-8')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def checked_path(root, relative):
    path = root / relative
    if Path(relative).is_absolute() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('스킨 준비 캐시 경로가 저장 폴더 밖입니다.')
    for part in (path, *path.parents):
        if part.is_symlink() or part.is_junction():
            raise ValueError('연결된 스킨 준비 캐시는 사용할 수 없습니다.')
        if part == root:
            return path
    raise ValueError('스킨 준비 캐시 경로가 잘못됐습니다.')


def read_entry(root, key, slot, changed, forbidden):
    pointer = json.loads(checked_path(root, slot + '.json').read_text(encoding='utf-8'))
    generation = pointer['generation']
    if not isinstance(generation, str) or not re.fullmatch('[0-9a-f]{32}', generation):
        raise ValueError('Invalid cache generation')
    folder = checked_path(root, generation)
    manifest = checked_path(root, generation + '/entry.json')
    if digest(manifest) != pointer['sha256']:
        raise ValueError('Cache manifest changed')
    entry = json.loads(manifest.read_text(encoding='utf-8'))
    if entry['format'] != FORMAT or entry['key'] != key:
        raise ValueError('Cache version changed')
    expected = {(kind, name) for kind in ('skin', 'original') for name in changed}
    result = []
    for saved in entry['records']:
        record = {name: saved[name] for name in FIELDS}
        identity = record['kind'], record['name']
        if identity not in expected or record['clone_bundle_name'] in forbidden:
            raise ValueError('Cache identities already loaded or mismatched')
        expected.remove(identity)
        for field, suffix in (('path', ''), ('expected_inventory', '.expected.json')):
            relative = f"{generation}/{record['kind']}/{record['name']}{suffix}"
            path = checked_path(root, relative)
            if digest(path) != saved[field + '_sha256']:
                raise ValueError('Cached skin file changed')
            record[field] = str(path)
        record['sha256'] = saved['path_sha256']
        result.append(record)
    if expected:
        raise ValueError('Incomplete skin cache')
    return result


def get_or_build(identity, changed, slot, forbidden, builder, progress=lambda s: None):
    """Use separate initial/retry identities; never replace a live generation."""
    if slot not in ('initial', 'retry'):
        raise ValueError('Invalid preparation slot')
    if any(Path(n).name != n or '/' in n or '\\' in n or ':' in n for n in changed):
        raise ValueError('Invalid bundle filename')
    key = hashlib.sha256(json.dumps(dict(format=FORMAT, identity=identity), sort_keys=True).encode()).hexdigest()
    app = data_root().resolve()
    root = checked_path(app, 'cache/prepared_skins/' + key)
    root.mkdir(parents=True, exist_ok=True)
    try:
        records = read_entry(root, key, slot, changed, set(forbidden))
    except (OSError, ValueError, KeyError, TypeError):
        records = None
    if records is not None:
        progress('저장된 스킨 준비 파일을 확인하고 재사용합니다…')
        return records

    # Publish a pointer only after every file was prepared and hashed. Old
    # generations stay intact because a running game may still reference them.
    generation = uuid.uuid4().hex
    folder = checked_path(root, generation)
    records = builder(folder)
    saved = []
    for record in records:
        item = {name: record[name] for name in FIELDS}
        for field in ('path', 'expected_inventory'):
            path = Path(record[field])
            checked_path(root, str(path.relative_to(root)))
            item[field + '_sha256'] = digest(path)
        saved.append(item)
    manifest = folder / 'entry.json'
    atomic_json(manifest, dict(format=FORMAT, key=key, records=saved))
    atomic_json(root / (slot + '.json'), dict(generation=generation, sha256=digest(manifest)))
    # Validate the new entry using the same checks as a future cache hit.
    return read_entry(root, key, slot, changed, set(forbidden))
