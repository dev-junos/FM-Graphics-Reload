"""Persistent bundle overlays with verified backups and recoverable transactions."""
from contextlib import contextmanager
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import uuid

from app_storage import data_root
import client
import skins
import full_skins


def atomic_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('x',encoding='utf-8') as stream:
            json.dump(value,stream,ensure_ascii=False,indent=2)
            stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:temporary.unlink(missing_ok=True)


def root_for(installed):
    key=hashlib.sha256(str(Path(installed).resolve()).casefold().encode('utf-8')).hexdigest()
    return data_root()/'installations'/key


@contextmanager
def lock(installed):
    handle=client.K.CreateMutexW(None,False,'Local\\FMGraphicsReloadFiles_'+root_for(installed).name)
    if not handle:raise C.WinError(C.get_last_error())
    acquired=False
    try:
        if client.K.WaitForSingleObject(handle,0) not in (0,0x80):
            raise RuntimeError('다른 적용 작업이 설치 파일을 변경하고 있습니다.')
        acquired=True;yield
    finally:
        if acquired:client.K.ReleaseMutex(handle)
        client.K.CloseHandle(handle)


def target_file(installed,name):
    if (not isinstance(name,str) or Path(name).name!=name or '/' in name or '\\' in name
            or ':' in name or not name.lower().endswith('.bundle')):
        raise ValueError('설치 파일 복구 기록의 파일 이름이 올바르지 않습니다.')
    target=installed/name
    if target.is_symlink() or target.is_junction() or target.resolve().parent!=installed:
        raise ValueError('연결된 설치 파일은 변경할 수 없습니다: '+name)
    return target


def blob_file(root,digest):
    if not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest):
        raise ValueError('설치 파일 백업 기록의 해시가 올바르지 않습니다.')
    target=root/'backups'/digest
    if target.is_symlink() or target.resolve().parent!=(root/'backups').resolve():
        raise ValueError('설치 파일 백업 경로가 올바르지 않습니다.')
    return target


def checked_copy(source,target,digest):
    target.parent.mkdir(parents=True,exist_ok=True)
    with Path(source).open('rb') as reader,target.open('xb') as writer:
        shutil.copyfileobj(reader,writer,1024*1024)
        writer.flush();os.fsync(writer.fileno())
    if skins._hash(target)!=digest:
        target.unlink()
        raise RuntimeError('복사 중 스킨 파일이 바뀌었습니다. 파일 수정을 마친 뒤 다시 적용해 주세요.')


def backup(root,source,digest):
    target=blob_file(root,digest)
    if target.exists():
        if skins._hash(target)!=digest:raise ValueError('설치 파일 백업이 손상되었습니다: '+str(target))
        return target
    temporary=target.with_name(digest+'.'+uuid.uuid4().hex+'.tmp')
    try:
        checked_copy(source,temporary,digest);os.replace(temporary,target)
    finally:temporary.unlink(missing_ok=True)
    return target


def read_state(installed):
    path=root_for(installed)/'state.json'
    if not path.exists():return dict(version=1,installed=str(installed),files={},transaction='')
    state=json.loads(path.read_text(encoding='utf-8'))
    if state.get('version')!=1 or state.get('installed','').casefold()!=str(installed).casefold() or not isinstance(state.get('files'),dict):
        raise ValueError('설치 파일 복구 기록을 확인해 주세요: '+str(path))
    for name,item in state['files'].items():
        target_file(installed,name)
        for field in ('original','applied'):
            if item[field] is not None:blob_file(root_for(installed),item[field])
    return state


def stage_folder(installed,transaction):
    if not re.fullmatch('[0-9a-f]{32}',transaction):raise ValueError('설치 파일 작업 기록이 올바르지 않습니다.')
    folder=installed/('.fmgr_'+transaction)
    if folder.is_symlink() or folder.is_junction() or folder.resolve().parent!=installed:
        raise ValueError('설치 파일 준비 경로가 올바르지 않습니다.')
    return folder


def cleanup_stage(folder):
    # Remove only direct temporary files in this validated, uniquely owned folder.
    if not folder.exists():return
    for path in folder.iterdir():
        if not path.is_file() or path.is_symlink():raise ValueError('설치 파일 준비 폴더에 예상하지 못한 항목이 있습니다.')
    for path in folder.iterdir():path.unlink()
    folder.rmdir()


def file_hash(path):
    return skins._hash(path) if path.exists() else None


def recover(installed,root,progress,pid=None):
    journal=root/'pending.json'
    if not journal.exists():return
    pending=json.loads(journal.read_text(encoding='utf-8'))
    if pending.get('installed','').casefold()!=str(installed).casefold():raise ValueError('설치 파일 복구 위치가 다릅니다.')
    stage=stage_folder(installed,pending['transaction'])
    if read_state(installed).get('transaction')!=pending['transaction']:
        progress('중단된 설치 파일 변경을 되돌리고 있습니다…')
        current_files={}
        for op in pending['operations']:
            target=target_file(installed,op['name']);digest=file_hash(target)
            current_files[op['name']]=digest
            if op['after'] is not None:blob_file(root,op['after'])
            if digest not in (op['before'],op['after']):
                raise ValueError('설치 파일이 외부에서 변경되어 자동 복구를 중단했습니다: '+op['name'])
            if op['before'] is not None:
                original=blob_file(root,op['before'])
                if not original.is_file() or skins._hash(original)!=op['before']:
                    raise ValueError('설치 파일 백업을 확인할 수 없습니다: '+op['name'])
        # FM may have started after a previous interrupted transaction. Its startup
        # bytes are the current mixture, not the files we are about to restore.
        capture_startup(pid,installed,current_files)
        stage.mkdir(exist_ok=True)
        for op in reversed(pending['operations']):
            target=target_file(installed,op['name']);digest=file_hash(target)
            if digest==op['before']:continue
            if digest!=op['after']:raise ValueError('복구 중 설치 파일이 외부에서 변경되었습니다: '+op['name'])
            if op['before'] is None:
                target.unlink();continue
            temporary=stage/('restore_'+uuid.uuid4().hex)
            checked_copy(blob_file(root,op['before']),temporary,op['before'])
            os.replace(temporary,target)
    cleanup_stage(stage);journal.unlink()


def capture_startup(pid,installed,files):
    """Capture untouched disk bytes before replacing them during this FM process."""
    if not pid:return
    folder=full_skins.session_folder(pid);path=folder/'startup.json'
    state=json.loads(path.read_text(encoding='utf-8')) if path.exists() else dict(installed=str(installed),files={})
    if state['installed'].casefold()!=str(installed).casefold():raise ValueError('게임 시작 스킨의 설치 위치가 다릅니다.')
    destination=folder/'startup';destination.mkdir(exist_ok=True)
    for name,digest in files.items():
        if digest is None:continue
        target=target_file(destination.resolve(),name)
        if name in state['files']:
            if not target.is_file() or skins._hash(target)!=state['files'][name]:
                raise ValueError('게임 시작 시 보관한 스킨 파일이 변경되었습니다: '+name)
            continue
        # A crash after the copy but before its metadata write leaves a verifiable file.
        if target.exists():
            if skins._hash(target)!=digest:raise ValueError('게임 시작 스킨 복사본을 확인하지 못했습니다: '+name)
        else:
            temporary=target.with_name(name+'.'+uuid.uuid4().hex+'.tmp')
            try:checked_copy(installed/name,temporary,digest);os.replace(temporary,target)
            finally:temporary.unlink(missing_ok=True)
        state['files'][name]=digest;atomic_json(path,state)


def ensure_process(pid):
    pids=client.fm_pids()
    if pids!=([pid] if pid else []):
        raise RuntimeError('게임 실행 상태가 바뀌었습니다. 연결 상태를 확인한 뒤 다시 적용해 주세요.')
    if pid and not client.request_token():raise RuntimeError('게임 진행 잠금을 먼저 확보해야 합니다.')


def sync(installed,winners,pid=None,progress=lambda s:None):
    if pid is not None:raise RuntimeError('설치 파일 저장은 FM 종료 후 처리합니다.')
    installed=Path(installed).resolve(strict=True);root=root_for(installed)
    with lock(installed):
        ensure_process(pid);root.mkdir(parents=True,exist_ok=True)
        recover(installed,root,progress,pid)
        state=read_state(installed);previous=state['files'];next_files={};operations=[];before={}
        names=sorted(set(previous)|set(winners))
        for index,name in enumerate(names):
            progress(f'설치 파일과 백업 확인 중… {index+1}/{len(names)}')
            target=target_file(installed,name);current=file_hash(target);before[name]=current
            old=previous.get(name)
            if old and current!=old['applied']:
                raise ValueError('설치 파일이 외부에서 변경되었습니다. 직접 수정한 파일을 기준으로 사용하려면 FM 종료 후 삭제 옆 메뉴의 스킨 기준 초기화를 사용해 주세요: '+name)
            baseline=old['original'] if old else current
            if old and baseline is not None:
                original=blob_file(root,baseline)
                if not original.is_file() or skins._hash(original)!=baseline:
                    raise ValueError('설치 파일 백업을 확인할 수 없습니다: '+name)
            if name in winners:
                source=Path(winners[name]);desired=skins._hash(source)
            else:source=blob_file(root,baseline) if baseline is not None else None;desired=baseline
            if desired!=baseline:next_files[name]=dict(original=baseline,applied=desired)
            if current!=desired:
                if current is not None:backup(root,target,current)
                operations.append(dict(name=name,before=current,after=desired,source=str(source) if source else None))
        # Preserve the first version seen by this process, even if a toggle only changes ownership.
        capture_startup(pid,installed,before)
        if not operations and next_files==previous:
            return dict(changed_files=[],active_files=len(previous),backup_folder=str(root/'backups'),installed=str(installed))
        transaction=uuid.uuid4().hex;stage=stage_folder(installed,transaction);stage.mkdir()
        committed=False
        try:
            for op in operations:
                if op['after'] is not None:checked_copy(op['source'],stage/op['name'],op['after'])
            pending=dict(transaction=transaction,installed=str(installed),operations=operations)
            ensure_process(pid)
            atomic_json(root/'pending.json',pending)
            for index,op in enumerate(operations):
                ensure_process(pid)
                target=target_file(installed,op['name'])
                if file_hash(target)!=op['before']:raise ValueError('적용 중 설치 파일이 외부에서 변경되었습니다: '+op['name'])
                progress(f'설치 스킨 파일 반영 중… {index+1}/{len(operations)}')
                if op['after'] is None:target.unlink()
                else:os.replace(stage/op['name'],target)
                if file_hash(target)!=op['after']:raise RuntimeError('설치 파일 교체 검증에 실패했습니다: '+op['name'])
            atomic_json(root/'state.json',dict(version=1,installed=str(installed),files=next_files,transaction=transaction))
            committed=True
        except Exception as exc:
            try:recover(installed,root,progress)
            except Exception as recovery:
                raise RuntimeError(f'설치 파일 변경이 중단되었고 복구를 마치지 못했습니다. 다음 적용 시 복구를 재시도합니다. {exc} / {recovery}') from exc
            raise RuntimeError(f'설치 파일 변경을 완료하지 못했습니다. 변경한 파일은 되돌렸습니다. 파일이 사용 중이면 FM을 종료한 뒤 다시 시도하세요. {exc}') from exc
        finally:
            if not (root/'pending.json').exists():cleanup_stage(stage)
        # A cleanup failure after commit must never be reported as a rolled-back apply.
        cleanup_error=''
        if committed:
            try:recover(installed,root,progress)
            except Exception as exc:cleanup_error=str(exc)
        return dict(changed_files=[op['name'] for op in operations],active_files=len(next_files),
                    backup_folder=str(root/'backups'),installed=str(installed),cleanup_error=cleanup_error)
