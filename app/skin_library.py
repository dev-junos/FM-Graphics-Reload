"""Persistent partial skin library; list order is highest priority first."""
from app_storage import data_root
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid
import client
import skins
import full_skins
import installation
import installed_skins
import live_skin_guard
from skin_import import discover, add, add_many, migrate_name, delete_managed
from text_codec import repair_import_names


def settings_path():
    return data_root()/'skins.json'


def empty():
    return dict(version=2,game_folder='',graphics_folder=client.default_folder(),skins=[])


def load(path=None):
    path=Path(path) if path else settings_path()
    if not path.exists():return empty()
    data=json.loads(path.read_text(encoding='utf-8'))
    if data.get('version') not in (1,2) or not isinstance(data.get('skins'),list):
        raise ValueError('스킨 목록 파일 형식을 확인해 주세요: '+str(path))
    ids=set()
    for item in data['skins']:
        if not all(isinstance(item.get(k),str) and item[k] for k in ('id','name','path')) or type(item.get('enabled')) is not bool or item['id'] in ids:
            raise ValueError('스킨 목록 항목 형식이 올바르지 않습니다: '+str(path))
        ids.add(item['id'])
        migrate_name(item)
    repair_import_names(data['skins'])
    data['version']=2
    data.pop('base_folder',None)
    data.setdefault('game_folder','')
    for key in ('game_folder','graphics_folder'):
        if not isinstance(data.get(key,''),str):raise ValueError('설정 폴더 경로 형식이 올바르지 않습니다.')
    return data


def save(data,path=None):
    path=Path(path) if path else settings_path()
    path.parent.mkdir(parents=True,exist_ok=True)
    value=dict(data,version=2);value.pop('base_folder',None)
    full_skins.save(path,value)


def remove(data,item_id):
    item=next(i for i in data['skins'] if i['id']==item_id)
    remaining=[i for i in data['skins'] if i['id']!=item_id]
    deleted=delete_managed(item,remaining)
    data['skins']=remaining
    return dict(deleted=deleted,managed=bool(item.get('managed')))


def preview(data,installed=None):
    """Fast file-only preview for the UI; hashing happens in the apply worker."""
    try:base=skins.normalize_folder(installed) if installed is not None else installation.locate(data)
    except (ValueError,OSError):
        if any(i['enabled'] for i in data['skins']):raise
        base=None
    base_files=skins.bundle_files(base) if base else {}
    providers={};entries={};enabled=[];missing=set()
    for item in data['skins']:
        entries[item['id']]=dict(item,files=0,wins=0,overridden=0)
        if not item['enabled']:continue
        folder=skins.normalize_folder(item['path']);files=skins.bundle_files(folder)
        unknown=files.keys()-base_files.keys()
        missing.update(unknown)
        enabled.append(item['id']);entries[item['id']]['files']=len(files)
        for name,path in files.items():
            providers.setdefault(name,[]).append(dict(id=item['id'],name=item['name'],path=str(path)))
    return dict(base=base,base_files=base_files,providers=providers,entries=entries,enabled=enabled,missing=sorted(missing))


def resolve(data,progress=lambda s:None,installed=None):
    """Resolve each whole bundle before comparing its winner to the original."""
    view=preview(data,installed)
    base=view['base'];base_files=view['base_files'];providers=view['providers'];entries=view['entries'];enabled=view['enabled']
    winners={};changed=[]
    for index,(name,choices) in enumerate(sorted(providers.items())):
        progress(f'선택한 스킨 파일 확인 중… {index+1}/{len(providers)}')
        winner=choices[0];entries[winner['id']]['wins']+=1
        for loser in choices[1:]:entries[loser['id']]['overridden']+=1
        digest=skins._hash(Path(winner['path']));original=skins._hash(base_files[name]) if name in base_files else None
        winners[name]=dict(winner,sha256=digest,original_sha256=original,base_path=str(base/name),providers=choices)
        if digest!=original:changed.append(name)
    signature=[dict(name=n,skin=winners[n]['sha256'],original=winners[n]['original_sha256']) for n in changed]
    key=hashlib.sha256(json.dumps(signature,sort_keys=True).encode()).hexdigest()
    return dict(key=key,base_folder=str(base),enabled=enabled,entries=entries,winners=winners,
                changed_bundles=changed,conflicts=[n for n,c in providers.items() if len(c)>1],original=not changed,uses_installed=not changed)


def compose(plan,cache=None,progress=lambda s:None):
    """Stage only winning changed files. Missing files always inherit the base."""
    if plan['original']:return None
    root=Path(cache) if cache else data_root()/'cache'/'overlays'
    root.mkdir(parents=True,exist_ok=True);destination=root/plan['key']
    if destination.is_dir():
        if all((destination/n).is_file() and skins._hash(destination/n)==plan['winners'][n]['sha256'] for n in plan['changed_bundles']):return destination
        raise ValueError('보관한 스킨 구성 파일이 변경됐습니다. cache 폴더를 확인해 주세요.')
    temporary=root/('preparing_'+uuid.uuid4().hex);temporary.mkdir()
    # Keep incomplete staging for diagnosis; it is never selected as a ready pack.
    for index,name in enumerate(plan['changed_bundles']):
        progress(f'우선순위에 따라 적용 파일 준비 중… {index+1}/{len(plan["changed_bundles"])}')
        target=temporary/name;shutil.copyfile(plan['winners'][name]['path'],target)
        if skins._hash(target)!=plan['winners'][name]['sha256']:
            raise RuntimeError('준비 중 스킨 파일이 바뀌었습니다. 파일 교체를 마친 뒤 다시 적용해 주세요.')
    full_skins.save(temporary/'composition.json',plan)
    temporary.rename(destination)
    return destination


def sync_disk(data,pid=None,progress=lambda s:None):
    installed=installation.locate(data,pid)
    view=preview(data,installed)
    winners={name:choices[0]['path'] for name,choices in view['providers'].items()}
    return installed_skins.sync(installed,winners,pid,progress)


def live_restrictions(data,pid):
    view=live_skin_guard.inventory(pid);blocked={}
    session_error=''
    statefile=data_root()/'logs'/'full_skin'/f'{pid}_{view["stamp"]}'/'session.json'
    if statefile.exists():
        try:
            state=json.loads(statefile.read_text(encoding='utf-8'))
            session_error=live_skin_guard.reason({b['name'] for b in state.get('records',[])},view)
        except (ValueError,OSError,KeyError,TypeError):session_error='이번 실행의 이전 스킨 자료를 확인하지 못해 스킨 적용을 차단했습니다.'
    for item in data['skins']:
        try:
            names=skins.bundle_files(skins.normalize_folder(item['path']))
            message=live_skin_guard.reason(names,view)
        except (ValueError,OSError) as exc:message=str(exc)
        if message:blocked[item['id']]=message
    return dict(pid=pid,blocked=blocked,checked={i['id']:i['path'] for i in data['skins']},installed=str(view['installed']),session_error=session_error)


def require_live_selection(data,pid):
    policy=live_restrictions(data,pid)
    if policy.get('session_error'):raise ValueError(policy['session_error'])
    errors=[i['name']+': '+policy['blocked'][i['id']] for i in data['skins'] if i['enabled'] and i['id'] in policy['blocked']]
    if errors:raise ValueError('\n'.join(errors))
    return policy


def only_disabling(previous,data):
    old=[(i['id'],i['path']) for i in previous['skins'] if i['enabled']]
    new=[(i['id'],i['path']) for i in data['skins'] if i['enabled']]
    return len(new)<len(old) and new==[key for key in old if key in new]


def configure(data,progress=lambda s:None):
    """No bridge needed for selection changes; only offline writes touch installation."""
    pids=client.fm_pids()
    if len(pids)>1:raise RuntimeError('FM26을 한 개만 실행해 주세요.')
    previous=load()
    view=preview(data,installation.locate(data,pids[0] if pids else None))
    if pids and not only_disabling(previous,data):require_live_selection(data,pids[0])
    # Keep deferred saves on this exact installation after process-based discovery ends.
    data['game_folder']=str(Path(view['base']).parents[3])
    if pids:
        if client.fm_pids()!=pids:raise ValueError('게임 실행 상태가 바뀌어 선택 저장을 중단했습니다.')
        data['disk_pending']=True
        save(data)
        return dict(deferred=True,changed_files=[],installed=str(view['base']))
    # Save the intent first. A crash after disk commit is retried idempotently.
    data['disk_pending']=True;save(data)
    try:result=sync_disk(data,progress=progress)
    except Exception:
        save(previous)
        raise
    data['disk_pending']=False
    try:save(data)
    except OSError as exc:result['settings_error']=str(exc)
    return result


def apply(pid,data,progress=lambda s:None):
    enabled=[i['name'] for i in data['skins'] if i['enabled']]
    result=dict(composition=dict(uses_installed=not enabled),enabled_skin_names=enabled,
                live_applied=False,restart_required=False)
    if not pid:return dict(result,offline=True,disk=configure(data,progress))
    if not client.request_token():raise RuntimeError('게임 진행 잠금을 먼저 확보해야 합니다.')
    require_live_selection(data,pid)
    installed=installation.locate(data,pid)
    view=preview(data,installed)
    if view['missing']:
        raise ValueError('설치 폴더에 없는 파일이 있습니다. FM을 종료한 뒤 스킨을 ON으로 켜면 추가할 수 있습니다: '+', '.join(view['missing']))
    try:
        with installed_skins.lock(installed):
            root=installed_skins.root_for(installed)
            if (root/'pending.json').exists():raise ValueError('중단된 설치 파일 작업이 있습니다. FM을 종료한 뒤 ON/OFF를 다시 시도해 주세요.')
            tracked=installed_skins.read_state(installed)['files']
            desired={name:Path(choices[0]['path']) for name,choices in view['providers'].items()}
            for name,record in tracked.items():
                if installed_skins.file_hash(installed_skins.target_file(installed,name))!=record['applied']:
                    raise ValueError('설치 파일이 외부에서 변경되었습니다. FM 종료 후 스킨 기준 초기화를 사용해 주세요: '+name)
                if name not in desired:
                    desired[name]=installed_skins.blob_file(root,record['original']) if record['original'] is not None else None
            removed=[name for name,path in desired.items() if path is None]
            if removed:raise ValueError('추가 설치 파일 삭제는 FM 종료 후 처리합니다: '+', '.join(removed))
            before={name:skins._hash(installed_skins.target_file(installed,name)) for name in desired}
            # Partial packs and startup backups do not necessarily include the
            # shared MonoScript catalog. Preserve it for metadata lookup, without
            # adding unchanged script bundles to the live replacement set.
            script_names={name for name in skins.bundle_files(installed) if name.endswith('_monoscripts.bundle')}
            with live_skin_guard.hold(pid,script_names):
                before.update({name:skins._hash(installed_skins.target_file(installed,name)) for name in script_names})
                installed_skins.capture_startup(pid,installed,before)
            folder=full_skins.session_folder(pid);metadata=folder/'startup.json'
            startup=json.loads(metadata.read_text(encoding='utf-8')) if metadata.exists() else dict(files={})
        # Hot apply reads desired sources directly; it never replaces open installation files.
        base=folder/'startup';winners={};changed=[]
        for name,digest in sorted(startup['files'].items()):
            original=installed_skins.target_file(base.resolve(),name)
            if not original.is_file() or skins._hash(original)!=digest:
                raise ValueError('게임 시작 시 보관한 스킨 파일이 변경되었습니다: '+name)
            source=desired.get(name,installed_skins.target_file(installed,name));current=skins._hash(source)
            winners[name]=dict(path=str(source),sha256=current,original_sha256=digest)
            if current!=digest:changed.append(name)
        signature=[dict(name=n,skin=winners[n]['sha256'],original=winners[n]['original_sha256']) for n in changed]
        key=hashlib.sha256(json.dumps(signature,sort_keys=True).encode()).hexdigest()
        plan=dict(key=key,winners=winners,changed_bundles=changed,original=not changed)
        source=compose(plan,progress=progress)
        require_live_selection(data,pid)
        live_skin_guard.require(pid,changed)
        live=full_skins.run(pid,source,restore=not changed,progress=progress,installed_override=base)
        result.update(live=live,live_applied=True)
    except Exception as exc:
        # Selection remains queued; installation files have not been touched.
        result.update(restart_required=True,live_error=str(exc))
    return result
