"""Fail-closed live bundle policy; no bridge injection or game writes."""
import ctypes as C
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import threading
import uuid
from contextlib import contextmanager
from app_storage import data_root
import client

_lock=threading.RLock()


def process_identity(pid):
    client.api('GetProcessTimes',[W.HANDLE]+[C.POINTER(C.c_uint64)]*4)
    handle=client.K.OpenProcess(0x1000,False,pid)
    if not handle:raise C.WinError(C.get_last_error())
    times=[C.c_uint64() for _ in range(4)]
    try:
        if not client.K.GetProcessTimes(handle,*(C.byref(t) for t in times)):
            raise C.WinError(C.get_last_error())
    finally:client.K.CloseHandle(handle)
    module=client.find_process_module(pid,'fm.exe')
    if not module:raise ValueError('실행 중인 FM 설치 위치를 확인하지 못해 스킨 적용을 차단했습니다.')
    # Never normalize to a child folder or fall back to a saved/different installation.
    folder=(Path(module.path).parent/'fm_Data/StreamingAssets/aa/StandaloneWindows64').resolve(strict=True)
    if not folder.is_dir():raise ValueError('실행 중인 FM의 정확한 스킨 폴더를 확인하지 못했습니다.')
    return times[0].value,folder


def inventory(pid):
    with _lock:
        if client.fm_pids()!=[pid]:raise ValueError('게임 실행 상태가 바뀌어 스킨 적용을 차단했습니다.')
        stamp,folder=process_identity(pid)
        birth_ns=(stamp-116444736000000000)*100
        current={}
        for file in folder.iterdir():
            if file.suffix.lower()!='.bundle':continue
            if file.is_symlink() or file.is_junction() or not file.is_file():continue
            if file.resolve().parent!=folder:continue
            key=file.name.lower()
            if key in current:raise ValueError('이름이 겹치는 설치 번들이 있어 스킨 적용을 차단했습니다.')
            stat=file.stat()
            current[key]=dict(path=str(file),modified=stat.st_mtime_ns,created=stat.st_ctime_ns,size=stat.st_size)
        if not current:raise ValueError('실행 중인 FM 설치 폴더의 번들을 확인하지 못했습니다.')
        record=data_root()/'logs'/'live_inventory'/f'{pid}_{stamp}.json'
        if record.exists():
            baseline=json.loads(record.read_text(encoding='utf-8'))
            if baseline.get('version')!=1 or baseline.get('installed')!=str(folder) or baseline.get('stamp')!=stamp or not isinstance(baseline.get('files'),dict):
                raise ValueError('이번 게임 실행의 번들 확인 기록이 일치하지 않습니다.')
        else:
            # Creation and modification times also reject files copied in after FM
            # started but before this app first observed it. Unknown files stay blocked.
            initial={n:v for n,v in current.items() if max(v['modified'],v['created'])<birth_ns and v['size']>0}
            baseline=dict(version=1,installed=str(folder),stamp=stamp,files=initial)
            record.parent.mkdir(parents=True,exist_ok=True)
            temporary=record.with_name(record.name+'.'+uuid.uuid4().hex+'.tmp')
            try:
                with temporary.open('x',encoding='utf-8') as stream:
                    json.dump(baseline,stream,ensure_ascii=False);stream.flush();os.fsync(stream.fileno())
                os.replace(temporary,record)
            finally:temporary.unlink(missing_ok=True)
        if client.fm_pids()!=[pid] or process_identity(pid)[0]!=stamp:
            raise ValueError('게임 실행 상태가 바뀌어 스킨 적용을 차단했습니다.')
        permitted={n for n,v in current.items() if n in baseline['files'] and v==baseline['files'][n]}
        return dict(pid=pid,stamp=stamp,installed=folder,current=current,permitted=permitted)


def reason(names,view):
    names=set(names)
    missing=sorted(names-set(view['current']))
    if missing:
        return '실행 중 추가 번들 차단: 설치 폴더에 없는 파일입니다. FM 종료 후 ON으로 적용해 주세요: '+', '.join(missing)
    unconfirmed=sorted(names-view['permitted'])
    if unconfirmed:
        return '실행 중 추가 번들 차단: 이번 실행 전에 존재한 파일로 확인되지 않거나 실행 중 변경된 파일입니다. FM 종료 후 적용해 주세요: '+', '.join(unconfirmed)
    return ''


def require(pid,names):
    view=inventory(pid);error=reason(names,view)
    if error:raise ValueError(error)
    return view


@contextmanager
def hold(pid,names):
    """Deny external writes/deletes to the checked installed files during native reload."""
    names=set(names);view=require(pid,names);handles=[]
    client.api('CreateFileW',[W.LPCWSTR,W.DWORD,W.DWORD,C.c_void_p,W.DWORD,W.DWORD,W.HANDLE],W.HANDLE)
    try:
        for name in sorted(names):
            handle=client.K.CreateFileW(view['current'][name]['path'],0x80000000,1,None,3,0x80,None)
            if handle==C.c_void_p(-1).value:
                raise ValueError('스킨 적용을 차단했습니다. 설치 번들의 읽기 전용 보호를 확보하지 못했습니다: '+name)
            handles.append(handle)
        require(pid,names)
        yield
    finally:
        for handle in handles:client.K.CloseHandle(handle)
