"""Reuse validated live bundles only as complete dependency-connected groups."""
import hashlib
import json
from pathlib import Path
from app_storage import data_root
from prepared_skin_cache import atomic_json, checked_path, digest


def signature(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def bundle_info(path, checksum, unity):
    """Cache disk dependency metadata, never game object IDs."""
    root = data_root().resolve()
    cache = checked_path(root, 'cache/bundle_dependencies/' + checksum + '.json')
    try:
        saved = json.loads(cache.read_text(encoding='utf-8'))
        info = saved['info']
        if saved['format'] != 1 or saved['sha256'] != signature(info):
            raise ValueError('Changed dependency index')
        if set(info) != {'owns', 'references'} or not all(
                isinstance(s, str) for values in info.values() for s in values):
            raise ValueError('Invalid dependency index')
        return info
    except (OSError, ValueError, KeyError, TypeError):
        pass
    env = unity.load(str(path))
    bundle = next(iter(env.files.values()))
    asset = next(o for o in env.objects if o.type.name == 'AssetBundle').read_typetree()
    # Match the exact identifiers prepare_copies rewrites. Include both CAB names
    # and the AssetBundle name; streamed-resource suffixes share the CAB prefix.
    owns = {node.split('.')[0] for node in bundle.files if node.startswith('CAB-')}
    owns.add(asset['m_Name'].split('.')[0])
    refs = set(asset.get('m_Dependencies', []))
    for file in bundle.files.values():
        refs.update(e.path for e in getattr(file, 'externals', []))
    info = dict(owns=sorted(owns), references=sorted(refs))
    if digest(path) != checksum:
        raise RuntimeError('준비 중 스킨 파일이 변경됐습니다. 다시 실행해 주세요.')
    cache.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(cache, dict(format=1, info=info, sha256=signature(info)))
    return info


def groups(infos):
    """Undirected components prevent mixing mutually dependent CAB generations."""
    edges = {name: set() for name in infos}
    for name, info in infos.items():
        for other, target in infos.items():
            if name != other and (set(info['owns']) & set(target['owns']) or
                    any(token in ref for token in target['owns'] for ref in info['references'])):
                edges[name].add(other); edges[other].add(name)
    remaining = set(infos)
    while remaining:
        pending = [min(remaining)]; component = set()
        while pending:
            name = pending.pop()
            if name in component:
                continue
            component.add(name); pending.extend(edges[name] - component)
        remaining -= component
        yield sorted(component)


def plan(source, installed, changed, identity, states, unity):
    """Return live records to share and a key for every requested bundle."""
    reusable = {}; keys = {}
    context = {k: v for k, v in identity.items() if k != 'files'}
    hashes = {r['name']: r for r in identity['files']}
    for kind, folder in (('skin', source), ('original', installed)):
        infos = {n: bundle_info(folder / n, hashes[n][kind], unity) for n in changed}
        for component in groups(infos):
            key = signature(dict(format=1, kind=kind, context=context,
                files=[dict(name=n, sha256=hashes[n][kind], dependencies=infos[n]) for n in component]))
            keys.update({(kind, n): key for n in component})
            for state in reversed(states):
                if not state.get('complete') or not state.get('assets_verified'):
                    continue
                candidates = {r['name']: r for r in state['records']
                              if r['kind'] == kind and r.get('pool_key') == key}
                if set(candidates) != set(component):
                    continue
                if not all('index' in r and Path(r.get('inventory', '')).is_file()
                           and Path(r.get('expected_inventory', '')).is_file()
                           for r in candidates.values()):
                    continue
                reusable.update({(kind, n): dict(r) for n, r in candidates.items()})
                break
    return reusable, keys


def unique_records(records):
    """A shared bundle occurs in several compositions but owns one live index."""
    result = []; seen = set()
    for record in records:
        key = (record['kind'], record.get('index'), record.get('clone_bundle_name'), record['name'])
        if key not in seen:
            seen.add(key); result.append(record)
    return result
