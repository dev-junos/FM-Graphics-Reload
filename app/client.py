"""Standalone graphics bridge client. No imports from the owner application."""
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import threading
import xml.etree.ElementTree as ET

from process_modules import find_process_module

from resources import ROOT, runtime_dll
BRIDGE_DLL='fm_skin_theme_probe_v10.dll'
BRIDGE_MAPPING='FMSkinThemeProbe10'
guard_context=threading.local()

def request_token():
    return getattr(guard_context,'token',0)
K = C.WinDLL('kernel32', use_last_error=True)
def api(name, args, result=W.BOOL):
    f = getattr(K, name); f.argtypes = args; f.restype = result; return f
api('OpenProcess', [W.DWORD, W.BOOL, W.DWORD], W.HANDLE)
api('CloseHandle', [W.HANDLE])
api('OpenFileMappingW', [W.DWORD, W.BOOL, W.LPCWSTR], W.HANDLE)
api('MapViewOfFile', [W.HANDLE,W.DWORD,W.DWORD,W.DWORD,C.c_size_t], C.c_void_p)
api('UnmapViewOfFile', [C.c_void_p])
api('CreateMutexW', [C.c_void_p,W.BOOL,W.LPCWSTR], W.HANDLE)
api('ReleaseMutex', [W.HANDLE])
api('WaitForSingleObject', [W.HANDLE,W.DWORD], W.DWORD)
api('GetTickCount64', [], C.c_uint64)
api('VirtualAllocEx', [W.HANDLE,C.c_void_p,C.c_size_t,W.DWORD,W.DWORD], C.c_void_p)
api('VirtualFreeEx', [W.HANDLE,C.c_void_p,C.c_size_t,W.DWORD])
api('WriteProcessMemory', [W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)])
api('GetModuleHandleW', [W.LPCWSTR], W.HMODULE)
api('GetProcAddress', [W.HMODULE,C.c_char_p], C.c_void_p)
api('CreateRemoteThread', [W.HANDLE,C.c_void_p,C.c_size_t,C.c_void_p,C.c_void_p,W.DWORD,C.c_void_p], W.HANDLE)
api('GetExitCodeThread', [W.HANDLE,C.POINTER(W.DWORD)])
api('CheckRemoteDebuggerPresent', [W.HANDLE,C.POINTER(W.BOOL)])

class Wire(C.Structure):
    _fields_ = [('magic',C.c_uint64),('version',C.c_uint64),('state',W.LONG),('code',W.DWORD),
                ('deadline',C.c_uint64),('heartbeat',C.c_uint64),('completions',C.c_uint64),
                ('panels',C.c_uint64),('operation',C.c_uint64),('path',W.WCHAR*1024),
                ('status_tick',C.c_uint64),('observed_world',C.c_uint64),('activity',W.LONG),('reserved',W.DWORD),
                ('guard_token',C.c_uint64),('lease_until',C.c_uint64),('request_token',C.c_uint64)]

class ProcessEntry(C.Structure):
    _fields_=[('dwSize',W.DWORD),('cntUsage',W.DWORD),('th32ProcessID',W.DWORD),
              ('th32DefaultHeapID',C.c_size_t),('th32ModuleID',W.DWORD),('cntThreads',W.DWORD),
              ('th32ParentProcessID',W.DWORD),('pcPriClassBase',W.LONG),('dwFlags',W.DWORD),('szExeFile',W.WCHAR*260)]

api('CreateToolhelp32Snapshot',[W.DWORD,W.DWORD],W.HANDLE)
api('Process32FirstW',[W.HANDLE,C.POINTER(ProcessEntry)])
api('Process32NextW',[W.HANDLE,C.POINTER(ProcessEntry)])


def fm_pids():
    # Find FM even when opening it is denied. Access denial must not mean "offline".
    snapshot=K.CreateToolhelp32Snapshot(2,0)
    if snapshot==C.c_void_p(-1).value:raise C.WinError(C.get_last_error())
    entry=ProcessEntry();entry.dwSize=C.sizeof(entry);result=[]
    try:
        valid=K.Process32FirstW(snapshot,C.byref(entry))
        while valid:
            if entry.szExeFile.lower()=='fm.exe':result.append(entry.th32ProcessID)
            valid=K.Process32NextW(snapshot,C.byref(entry))
        if C.get_last_error()!=18:raise C.WinError(C.get_last_error())
    finally:K.CloseHandle(snapshot)
    return sorted(result)

def validate_folder(folder):
    if not str(folder).strip(): raise ValueError('그래픽 폴더를 선택해 주세요.')
    p=Path(folder).expanduser().resolve(strict=True)
    if not p.is_dir(): raise ValueError('폴더를 선택해 주세요.')
    if len((str(p)+'\0').encode('utf-16-le'))>2048: raise ValueError('폴더 경로가 너무 깁니다.')
    count=0; mappings=0
    for base,dirs,files in os.walk(p):
        if 'config.xml' not in {f.lower() for f in files}: continue
        for name in files:
            if name.lower()!='config.xml': continue
            config=Path(base)/name
            try: tree=ET.parse(config)
            except ET.ParseError as exc: raise ValueError(f'config.xml 형식 오류: {config}\n{exc}') from exc
            records=[r for r in tree.iter('record') if r.get('from') and r.get('to')]
            count+=1; mappings+=len(records)
    if not mappings: raise ValueError('이미지 연결이 들어 있는 config.xml을 찾지 못했습니다. 그래픽팩 폴더를 선택해 주세요.')
    return p,count,mappings

def default_folder():
    shell=C.WinDLL('shell32'); buf=C.create_unicode_buffer(32768)
    shell.SHGetFolderPathW.argtypes=[W.HWND,C.c_int,W.HANDLE,W.DWORD,W.LPWSTR]
    if shell.SHGetFolderPathW(None,5,None,0,buf)!=0: return ''
    p=Path(buf.value)/'Sports Interactive'/'Football Manager 26'/'graphics'
    return str(p) if p.is_dir() else ''

def verify_build(pid):
    profile=json.loads((ROOT/'runtime/profile.json').read_text(encoding='utf-8'))
    for name,expected in profile['hashes'].items():
        module=find_process_module(pid,name)
        if not module: raise RuntimeError(f'FM26 게임 모듈을 찾지 못했습니다: {name}')
        with Path(module.path).open('rb') as f: actual=hashlib.file_digest(f,'sha256').hexdigest()
        if actual!=expected: raise RuntimeError('현재 FM 빌드는 지원하지 않습니다. 이 시험판은 FM26 26.3.2 전용입니다.')

def install(pid):
    verify_build(pid)
    # Do not stack release hooks over older/research bridges in the same process.
    legacy=['fm_graphics_reload_v1.dll','fm_graphics_reload_v2.dll']+[f'fm_skin_theme_probe_v{i}.dll' for i in range(1,10)]
    if any(find_process_module(pid,name) for name in legacy):
        raise RuntimeError('이 게임에는 이전 버전 연결 모듈이 남아 있습니다. 저장 후 FM을 재시작한 뒤 0.9 버전을 사용해 주세요.')
    dll=runtime_dll(BRIDGE_DLL)
    existing=find_process_module(pid,dll.name)
    if existing:
        if Path(existing.path).read_bytes()!=dll.read_bytes():raise RuntimeError('게임에 연결된 모듈과 프로그램 버전이 다릅니다. FM을 재시작해 주세요.')
        return
    import pefile
    with pefile.PE(str(dll)) as pe:
        rva=next(s.address for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name==b'StartSkinThemeProbe')
    h=K.OpenProcess(0x43a,False,pid)
    if not h: raise C.WinError(C.get_last_error())
    allocation=None
    def remote_call(address,arg):
        nonlocal allocation
        thread=K.CreateRemoteThread(h,None,0,address,arg,0,None)
        if not thread: raise C.WinError(C.get_last_error())
        try:
            if K.WaitForSingleObject(thread,15000)!=0:
                # The remote thread might still read its argument. Do not free it.
                allocation=None
                raise TimeoutError('게임 연결 완료를 확인하지 못했습니다. 자동으로 재실행하지 않습니다.')
            code=W.DWORD()
            if not K.GetExitCodeThread(thread,C.byref(code)): raise C.WinError(C.get_last_error())
            return code.value
        finally: K.CloseHandle(thread)
    try:
        debug=W.BOOL()
        if not K.CheckRemoteDebuggerPresent(h,C.byref(debug)) or debug.value: raise RuntimeError('게임 디버거를 해제한 뒤 사용해 주세요.')
        local=K.GetProcAddress(K.GetModuleHandleW('kernel32.dll'),b'LoadLibraryW'); loader=None
        for name in ('kernel32.dll','KernelBase.dll'):
            lm=find_process_module(os.getpid(),name); rm=find_process_module(pid,name)
            if lm and rm and lm.base<=local<lm.base+lm.size: loader=rm.base+local-lm.base; break
        if not loader: raise RuntimeError('게임 연결 함수를 찾지 못했습니다.')
        raw=(str(dll)+'\0').encode('utf-16-le'); allocation=K.VirtualAllocEx(h,None,len(raw),0x3000,4)
        got=C.c_size_t()
        if not allocation or not K.WriteProcessMemory(h,allocation,C.create_string_buffer(raw),len(raw),C.byref(got)) or got.value!=len(raw): raise C.WinError(C.get_last_error())
        remote_call(loader,allocation)
        module=find_process_module(pid,dll.name)
        if not module: raise RuntimeError('연결 모듈을 불러오지 못했습니다.')
        code=remote_call(module.base+rva,None)
        if code: raise RuntimeError(f'연결 모듈 초기화 실패 ({code}). 게임을 다시 시작해야 할 수 있습니다.')
    finally:
        if allocation: K.VirtualFreeEx(h,allocation,0,0x8000)
        K.CloseHandle(h)

ERRORS={2:'요청 기한이 지났거나 디버거가 연결돼 있습니다.',3:'그래픽 폴더가 올바르지 않습니다.',
        10:'게임 내부 함수를 찾지 못했습니다.',11:'게임이 그래픽 처리 중 오류를 반환했습니다.',12:'게임 화면 객체를 확인하지 못했습니다.',
        20:'게임이 대기 상태가 아닙니다. 저장·로드·날짜 진행이 끝난 뒤 다시 눌러 주세요.',
        21:'읽기 완료를 5분 안에 확인하지 못했습니다. 화면 갱신은 실행하지 않았습니다. 게임을 재시작한 뒤 다시 시도해 주세요.',
        22:'처리 중 다른 게임이 로드되어 화면 갱신을 중단했습니다.',23:'게임의 그래픽 읽기 작업이 실패했습니다.',
        24:'그래픽 등록은 끝났지만 게임이 진행 중이어서 화면 갱신을 중단했습니다.',
        25:'게임 진행 잠금을 확인할 수 없습니다. 게임 연결을 다시 확인해 주세요.',
        26:'게임 창의 입력을 잠글 수 없습니다. 일반 게임 화면에서 다시 시도해 주세요.'}

def request(pid,folder='',preflight=False,progress=lambda s:None):
    mutex=K.CreateMutexW(None,False,f'Local\\FMGraphicsReloadClient1_{pid}')
    if not mutex: raise C.WinError(C.get_last_error())
    acquired=False; mapping=None; ptr=None
    try:
        if K.WaitForSingleObject(mutex,0) not in (0,0x80): raise RuntimeError('다른 새로고침 작업이 실행 중입니다.')
        acquired=True
        progress('게임 버전과 연결 상태를 확인하고 있습니다…')
        install(pid)
        mapping=K.OpenFileMappingW(0xf001f,False,f'Local\\{BRIDGE_MAPPING}_{pid}')
        if not mapping: raise RuntimeError('연결 모듈이 준비되지 않았습니다. 게임을 다시 시작해 주세요.')
        ptr=K.MapViewOfFile(mapping,0xf001f,0,0,C.sizeof(Wire))
        if not ptr: raise C.WinError(C.get_last_error())
        wire=Wire.from_address(ptr)
        if wire.magic!=0x464d475241504831 or wire.version!=1: raise RuntimeError('연결 모듈 버전이 맞지 않습니다.')
        if wire.state in (1,2): raise RuntimeError('이전 요청이 아직 처리 중입니다. 완료 전에는 다시 실행할 수 없습니다.')
        if wire.state==4 and wire.code==21: raise RuntimeError(ERRORS[21])
        end=time.monotonic()+2
        while not wire.heartbeat and time.monotonic()<end:time.sleep(.05)
        if not wire.heartbeat:raise RuntimeError('게임 화면의 응답을 확인하지 못했습니다. FM을 재시작한 뒤 사용해 주세요.')
        wire.path=str(folder); wire.operation=1 if preflight else 2; wire.code=0;wire.request_token=request_token()
        wire.deadline=K.GetTickCount64()+(10000 if preflight else 300000)
        before=(wire.completions,wire.panels); wire.state=1
        progress('게임에서 그래픽을 읽고 있습니다. 완료될 때까지 게임을 진행하지 마세요…')
        until=time.monotonic()+(15 if preflight else 305)
        while wire.state in (1,2):
            if time.monotonic()>until: raise TimeoutError('게임 응답을 확인하지 못했습니다. 요청이 남아 있을 수 있어 자동 재시도하지 않습니다.')
            time.sleep(.05)
        if wire.state!=3: raise RuntimeError(ERRORS.get(wire.code,f'그래픽 갱신 실패 ({wire.code})'))
        return dict(pid=pid,folder=str(folder),preflight=preflight,
                    registration_completions=wire.completions-before[0],panel_reloads=wire.panels-before[1])
    finally:
        if ptr: K.UnmapViewOfFile(ptr)
        if mapping: K.CloseHandle(mapping)
        if acquired: K.ReleaseMutex(mutex)
        K.CloseHandle(mutex)
