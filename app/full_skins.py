"""Retained full-pack switching; installation files are only read."""
from app_storage import data_root
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import time
import uuid
import client
import skins
import live_skin_guard
import prepared_skin_cache
import skin_pool
from bundle_inventory import script_catalog, required_assets, validate_records, AssetInventoryError

def read_rows(path):
    return [json.loads(s) for s in Path(path).read_text(encoding='utf-8').splitlines() if s]

def group(rows):
    result=defaultdict(list)
    for row in rows:result[row['class'],row['name']].append(row)
    return result

def save(path,value):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(path)

def session_folder(pid):
    import ctypes as C
    from ctypes import wintypes as W
    client.api('GetProcessTimes',[W.HANDLE]+[C.POINTER(C.c_uint64)]*4)
    handle=client.K.OpenProcess(0x1000,False,pid)
    if not handle:raise C.WinError(C.get_last_error())
    times=[C.c_uint64() for _ in range(4)]
    try:
        if not client.K.GetProcessTimes(handle,*(C.byref(t) for t in times)):raise C.WinError(C.get_last_error())
    finally:client.K.CloseHandle(handle)
    key=f'{pid}_{times[0].value}'
    folder=data_root()/'logs'/'full_skin'/key
    # Reuse the state owned by an identical, already loaded bridge after an app update.
    existing=client.find_process_module(pid,client.BRIDGE_DLL)
    if existing and not (folder/'session.json').exists():
        dll=Path(existing.path);candidate=dll.parent.parent/'logs'/'full_skin'/key
        local=client.ROOT/'runtime'/client.BRIDGE_DLL
        if (candidate/'session.json').is_file() and local.is_file() and skins._hash(dll)==skins._hash(local):folder=candidate
    folder.mkdir(parents=True,exist_ok=True)
    return folder

def fingerprint(source,installed,changed):
    files=[{'name':n,'skin':skins._hash(source/n),'original':skins._hash(installed/n)} for n in sorted(changed)]
    key=hashlib.sha256(('verified-assets-v2:'+json.dumps(files,sort_keys=True)).encode()).hexdigest()
    return key,files

def prepare_copies(source,installed,changed,dest,progress=lambda s:None):
    from unity_support import unitypy
    UnityPy=unitypy()
    from UnityPy.streams import EndianBinaryReader
    records=[]
    nonce=uuid.uuid4().hex
    for kind,folder in [('skin',source),('original',installed)]:
        target_folder=dest/kind;target_folder.mkdir(parents=True)
        catalog=script_catalog(folder,installed,UnityPy)
        replacements={};items=[]
        for name in changed:
            env=UnityPy.load(str(folder/name));bundle=next(iter(env.files.values()))
            for node in bundle.files:
                base=node.split('.')[0]
                if base.startswith('CAB-'):replacements[base]='CAB-'+hashlib.sha256(f'{nonce}:{kind}:{base}'.encode()).hexdigest()[:32]
            ab=next(o for o in env.objects if o.type.name=='AssetBundle').read_typetree()
            expected=target_folder/(name+'.expected.json')
            save(expected,required_assets(env,catalog))
            base=ab['m_Name'].split('.')[0]
            if len(base)!=32:raise ValueError('지원하지 않는 번들 내부 이름입니다: '+name)
            replacements[base]=hashlib.sha256(f'{nonce}:{kind}:bundle:{base}'.encode()).hexdigest()[:32]
            items.append(dict(name=name,kind=kind,objects=len(env.objects),expected_inventory=str(expected),original_bundle_name=ab['m_Name'],clone_bundle_name=ab['m_Name'].replace(base,replacements[base],1)))
        for i,item in enumerate(items):
            progress(f'스킨과 원복 자료 준비 중… {kind} {i+1}/{len(items)}')
            env=UnityPy.load(str(folder/item['name']));bundle=next(iter(env.files.values()));files={}
            for node,file in bundle.files.items():
                data=file.save() if hasattr(file,'save') else file.bytes
                for old,new in replacements.items():
                    if len(old)!=len(new):raise ValueError('번들 식별자 길이가 맞지 않습니다.')
                    data=data.replace(old.encode(),new.encode());node=node.replace(old,new)
                reader=EndianBinaryReader(data);reader.flags=file.flags;files[node]=reader
            bundle.files=files;target=target_folder/item['name'];target.write_bytes(bundle.save(packer='lz4'))
            check=UnityPy.load(str(target))
            if len(check.objects)!=item['objects']:raise ValueError('스킨 복사본 자원 수가 원본과 다릅니다.')
            item.update(path=str(target),sha256=skins._hash(target));records.append(item)
    save(dest/'manifest.json',records)
    return records


def preparation_identity(source,installed,changed):
    from resources import resource
    from unity_support import unitypy
    dependencies=[]
    for kind,folder in [('skin',source),('original',installed)]:
        dependencies.extend(dict(kind=kind,name=p.name,sha256=skins._hash(p))
                            for p in sorted(folder.glob('*_monoscripts.bundle')))
    return dict(files=fingerprint(source,installed,changed)[1],scripts=dependencies,
                profile=skins._hash(resource('runtime/profile.json')),
                unitypy=unitypy().__version__)


def cached_copies(source,installed,changed,slot,states,progress):
    identity=preparation_identity(source,installed,changed)
    forbidden={b['clone_bundle_name'] for state in states
               for b in state.get('records',[])+state.get('rejected',[])}
    def build(dest):
        records=prepare_copies(source,installed,changed,dest,progress)
        if preparation_identity(source,installed,changed)!=identity:
            raise RuntimeError('준비 중 스킨 파일이 변경됐습니다. 파일 교체가 끝난 뒤 다시 실행해 주세요.')
        return records
    records=prepared_skin_cache.get_or_build(identity,changed,slot,forbidden,
                                            build,progress)
    if preparation_identity(source,installed,changed)!=identity:
        raise RuntimeError('준비 중 스킨 파일이 변경됐습니다. 파일 교체가 끝난 뒤 다시 실행해 주세요.')
    return records


def shared_copies(source,installed,changed,states,capacity,progress):
    from unity_support import unitypy
    identity=preparation_identity(source,installed,changed)
    shared,keys=skin_pool.plan(source,installed,changed,identity,states,unitypy())
    needed=2*len(changed)-len(shared)
    if needed>capacity:
        raise RuntimeError(f'스킨 보관 공간이 부족합니다. 추가 {needed}개 / 남은 {capacity}개. FM을 다시 시작한 뒤 적용해 주세요.')
    names=sorted({name for kind,name in keys if (kind,name) not in shared})
    fresh=cached_copies(source,installed,names,'initial',states,progress) if names else []
    choices={(r['kind'],r['name']):r for r in fresh}
    choices.update(shared)
    records=[dict(choices[k],pool_key=key,shared=k in shared) for k,key in keys.items()]
    if preparation_identity(source,installed,changed)!=identity:
        raise RuntimeError('준비 중 스킨 파일이 변경됐습니다. 다시 실행해 주세요.')
    progress(f'불러온 스킨 자원 재사용 {len(shared)}/{len(records)} · 새로 불러오기 {needed}개')
    return records


def load_verified_assets(connection,pid,changed,source,installed,pack_folder,state,statefile,progress):
    """A failed deserialization is sticky; retry once with fresh CAB identities."""
    for attempt in range(2):
        records=state['records']
        for i,b in enumerate(records):
            if b.get('shared'):continue
            live_skin_guard.require(pid,changed)
            progress(f'스킨 파일을 불러오는 중… {i+1}/{len(records)}')
            b['index']=connection.command(22,Path(b['path']))['matching_styles'];save(statefile,state)
        for i,b in enumerate(records):
            if b.get('shared'):continue
            progress(f'화면 자원 확인 중… {i+1}/{len(records)}')
            dest=pack_folder/f"{b['kind']}_{b['index']}_assets.jsonl"
            connection.command(23,dest,index=b['index']);b['inventory']=str(dest);save(statefile,state)
        try:
            validate_records(records)
        except AssetInventoryError as exc:
            save(pack_folder/f'validation_failed_{attempt}.json',exc.failures)
            # Keep failed objects alive but never use them for matching or routing.
            reused=[b for b in records if b.get('shared')]
            rejected=[b for b in records if not b.get('shared')]
            state.setdefault('rejected',[]).extend(rejected)
            state['records']=[];state['validation_error']=exc.failures;save(statefile,state)
            if attempt or status(connection,pack_folder)['bundles']+len(rejected)>240:
                raise
            progress('일부 스킨 자원의 첫 연결을 다시 준비합니다…')
            live_skin_guard.require(pid,changed)
            retry_names=sorted({b['name'] for b in rejected})
            copies=cached_copies(source,installed,retry_names,'retry',
                                 [state]+state.get('previous',[]),progress)
            wanted={(b['kind'],b['name']):b for b in rejected}
            state['records']=reused+[dict(b,**({'pool_key':wanted[b['kind'],b['name']]['pool_key']}
                if 'pool_key' in wanted[b['kind'],b['name']] else {}))
                for b in copies if (b['kind'],b['name']) in wanted]
            if fingerprint(source,installed,changed)[0]!=state['key']:
                raise RuntimeError('재확인 중 스킨 파일이 변경됐습니다. 다시 실행해 주세요.')
            state['retry_count']=1;save(statefile,state)
        else:
            state.pop('validation_error',None)
            state['assets_verified']=True;save(statefile,state)
            return

def make_routes(original_rows,current_rows,records,dest,previous_records=()):
    original=group(original_rows);current=group(current_rows)
    mods={b['name']:b for b in records if b['kind']=='skin'}
    bases={b['name']:b for b in records if b['kind']=='original'}
    skin_global=group([r for b in mods.values() for r in read_rows(b['inventory'])])
    live_pairs=[];base_pairs=[];routes=[];ambiguous=[];seen=set()
    previous_original=defaultdict(list)
    for b in previous_records:
        if b['kind']=='original':previous_original[b['name']].append(b)
    for name,bundle in mods.items():
        before=group(read_rows(bases[name]['inventory']));after=group(read_rows(bundle['inventory']))
        missing=set(before)-set(after)
        if missing:
            dest.mkdir(exist_ok=True)
            save(dest/'incompatible.json',dict(bundle=name,missing=[dict(type=k[0],name=k[1]) for k in sorted(missing)]))
            details=', '.join(k[1] or k[0] for k in sorted(missing)[:4])
            raise ValueError(f'실행 중 스킨 교체에 필요한 기존 자원 {len(missing)}개가 새 스킨에 없습니다: {name} · {details}')
        for key,old in before.items():
            new=after[key]
            if len(old)!=1 or len(new)!=1:
                ambiguous.append([name,*key,len(old),len(new)]);continue
            if not key[1]:continue
            base_pairs.append([old[0]['id'],new[0]['id'],name,key]);seen.add(old[0]['id'])
            if len(original[key])==1 and len(skin_global[key])==1:
                o=original[key][0]
                if o['id'] not in seen:
                    live_pairs.append([o['id'],new[0]['id'],name,key]);seen.add(o['id'])
        # A screen first opened under a previous skin may use its retained baseline.
        for previous_bundle in previous_original[name]:
            previous=group(read_rows(previous_bundle['inventory']))
            for key,old in previous.items():
                new=after.get(key,[])
                if len(old)==1 and len(new)==1 and key[1] and old[0]['id'] not in seen:
                    if old[0]['id']!=before.get(key,[{}])[0].get('id'):
                        base_pairs.append([old[0]['id'],new[0]['id'],name,key]);seen.add(old[0]['id'])
        candidates=current['UnityEngine.AssetBundle',bundle['clone_bundle_name']]
        if len(candidates)!=1:raise ValueError('게임에 불러온 스킨 묶음을 식별하지 못했습니다.')
        routes.append([bundle['original_bundle_name'],candidates[0]['id']])
    pairs=live_pairs+base_pairs
    if not pairs:raise ValueError('교체할 스킨 자원 연결이 없습니다.')
    if len(pairs)>500000:raise ValueError(f'스킨 연결 {len(pairs):,}개가 처리 한도 500,000개를 넘었습니다.')
    dest.mkdir(exist_ok=True)
    (dest/'pairs.txt').write_text(''.join(f'{p[0]} {p[1]}\n' for p in pairs),encoding='ascii')
    (dest/'bundles.txt').write_text(''.join(f'{n} {i}\n' for n,i in routes),encoding='ascii')
    report=dict(live_pairs=live_pairs,baseline_pairs=base_pairs,routes=routes,ambiguous=ambiguous)
    save(dest/'report.json',report)
    return report

def status(connection,folder):
    path=folder/f'status_{time.time_ns()}.json'
    connection.command(32,path)
    return json.loads(path.read_text(encoding='utf-8'))

def restore_active(connection,folder,current,progress):
    if not current['active']:
        return dict(restored=True,already_original=True,status=current)
    progress('추가 스킨을 해제하고 게임 시작 시의 스킨으로 연결합니다…')
    result=connection.command(31,folder)
    check=status(connection,folder)
    if check['active']:raise RuntimeError('스킨 원복 상태를 확인하지 못했습니다.')
    return dict(result,restored=True,status=check)

def run(pid,source=None,restore=False,progress=lambda s:None,installed_override=None):
    names=set(skins.bundle_files(skins.normalize_folder(source))) if not restore else set()
    statefile=session_folder(pid)/'session.json'
    state=json.loads(statefile.read_text(encoding='utf-8')) if statefile.exists() else {}
    names.update(b['name'] for b in state.get('records',[]))
    with live_skin_guard.hold(pid,names):
        return _run(pid,source,restore,progress,installed_override)


def _run(pid,source=None,restore=False,progress=lambda s:None,installed_override=None):
    names=set(skins.bundle_files(skins.normalize_folder(source))) if not restore else set()
    live_skin_guard.require(pid,names)
    if restore and not client.find_process_module(pid,client.BRIDGE_DLL):
        return dict(pid=pid,scope='full_skin',restored=True,already_original=True,status=dict(active=False,bundles=0),uses_installed=True)
    folder=session_folder(pid);statefile=folder/'session.json'
    state=json.loads(statefile.read_text(encoding='utf-8')) if statefile.exists() else {}
    if state:
        live_skin_guard.require(pid,{b['name'] for b in state.get('records',[])})
    with skins.Session(pid) as connection:
        current=status(connection,folder)
        if restore:
            return dict(restore_active(connection,folder,current,progress),pid=pid,scope='full_skin',evidence=str(folder))
        source=skins.normalize_folder(source)
        installed=skins.normalize_folder(installed_override) if installed_override is not None else skins.installed_folder(pid)
        progress('설치 폴더와 선택한 스킨 파일을 비교합니다…')
        analysis=skins.analyze(source,installed,progress)
        if analysis['added_bundles']:raise ValueError('새 카탈로그가 필요한 추가 번들은 지원하지 않습니다: '+', '.join(analysis['added_bundles']))
        changed=analysis['changed_bundles']
        if not changed:
            return dict(restore_active(connection,folder,current,progress),pid=pid,scope='full_skin',evidence=str(folder))
        key,files=fingerprint(source,installed,changed)
        if current['active']:
            if state.get('key')==key:return dict(pid=pid,scope='full_skin',restored=False,already_applied=True,changed_bundles=changed,evidence=str(folder),status=current)
        if not state and current['bundles']:
            raise ValueError('다른 폴더에서 준비한 스킨 자료가 게임에 남아 있습니다. 처음 사용한 프로그램 폴더에서 계속 사용해 주세요.')
        history=state.get('previous',[])
        if state and state.get('key')!=key:
            old=dict(state);old.pop('previous',None);history=history+[old]
            matches=[p for p in history if p['key']==key]
            state=dict(matches[-1]) if matches else {}
        previous_records=skin_pool.unique_records([b for p in history if p['key']!=key for b in p['records']])
        pack_folder=Path(state.get('folder',folder)) if state else folder/('pack_'+uuid.uuid4().hex)
        pack_folder.mkdir(exist_ok=True)
        if not state:
            if len(changed)>100:raise ValueError('이번 시험판은 변경 번들 100개 이하를 지원합니다.')
            records=shared_copies(source,installed,changed,history,240-current['bundles'],progress)
            if fingerprint(source,installed,changed)[0]!=key:raise RuntimeError('준비 중 스킨 파일이 변경됐습니다. 파일 교체가 끝난 뒤 다시 실행해 주세요.')
            # Validate and stage disk copies before changing a currently active skin.
            current=restore_active(connection,folder,current,progress)['status']
            connection.command(33,folder)
            state=dict(key=key,folder=str(pack_folder),source=str(source),installed=str(installed),files=files,records=records,complete=False,previous=history)
            save(statefile,state)
            load_verified_assets(connection,pid,changed,source,installed,pack_folder,state,statefile,progress)
            state['complete']=True;save(statefile,state)
        if not state.get('complete'):raise RuntimeError('이전 스킨 준비가 완료되지 않았습니다. FM을 다시 시작한 뒤 시도해 주세요.')
        validate_records(state['records'])
        current=restore_active(connection,folder,current,progress)['status']
        # One fresh inventory supplies both bundle lookup and routing. The former
        # pre-load/debug inventories were overwritten before any route used them.
        # Refresh on reuse too: screens opened since the last apply add original assets.
        inventory=pack_folder/f'live_{time.time_ns()}.jsonl';connection.command(20,inventory)
        rows=read_rows(inventory)
        rejected=state.get('rejected',[])+[b for p in history for b in p.get('rejected',[])]
        excluded={r['id'] for b in skin_pool.unique_records(previous_records+state['records']+rejected) for r in read_rows(b['inventory'])}
        originals=[r for r in rows if r['id'] not in excluded]
        make_routes(originals,rows,state['records'],pack_folder/'routes',previous_records)
        state['previous']=history;save(statefile,state)
        progress('추가 스킨의 적용·해제 연결을 검사합니다…')
        connection.command(33,folder);connection.command(28,pack_folder/'routes')
        preflight=connection.command(29,folder)
        if not preflight['matching_styles']:raise RuntimeError('교체할 게임 자원 참조가 없습니다.')
        progress('전체 스킨을 적용하고 화면을 다시 불러옵니다…')
        live_skin_guard.require(pid,changed)
        result=connection.command(30,pack_folder/'routes');check=status(connection,folder)
        if not check['active']:raise RuntimeError('전체 스킨 적용 상태를 확인하지 못했습니다.')
    return dict(result,pid=pid,scope='full_skin',restored=False,changed_bundles=changed,source=str(source),evidence=str(folder),status=check)
