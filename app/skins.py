"""Bundle analysis and the verified, in-place common stylesheet operation."""
from app_storage import data_root
import ctypes as C
import hashlib
import json
from pathlib import Path
import time
import uuid
import client

STYLE_BUNDLE='ui-styles_assets_default.bundle'
STYLE_FIELDS={'m_Rules','m_ComplexSelectors','colors','floats','strings','dimensions'}

def installed_folder(pid):
    module=client.find_process_module(pid,'fm.exe')
    if not module:raise RuntimeError('FM 설치 폴더를 찾지 못했습니다.')
    return Path(module.path).parent/'fm_Data/StreamingAssets/aa/StandaloneWindows64'

def normalize_folder(value):
    if not str(value or '').strip():raise ValueError('스킨 파일이 들어 있는 폴더를 선택해 주세요.')
    p=Path(value).expanduser().resolve(strict=True)
    if not p.is_dir():raise ValueError('스킨 폴더를 선택해 주세요.')
    if not bundle_files(p) and bundle_files(p/'StandaloneWindows64'):p=p/'StandaloneWindows64'
    if not bundle_files(p):raise ValueError('.bundle 파일이 들어 있는 스킨 폴더를 선택해 주세요.')
    return p

def bundle_files(folder):
    return {p.name.lower():p for p in Path(folder).glob('*') if p.is_file() and p.suffix.lower()=='.bundle' and not p.name.lower().startswith('_bak_')}

def _hash(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def analyze(source,installed,progress=lambda s:None):
    source=normalize_folder(source);installed=normalize_folder(installed)
    base=bundle_files(installed);other=bundle_files(source)
    changed=[]
    for i,name in enumerate(sorted(base.keys()&other.keys())):
        progress(f'스킨 파일 비교 중… {i+1}/{len(base.keys()&other.keys())}')
        if base[name].stat().st_size!=other[name].stat().st_size or _hash(base[name])!=_hash(other[name]):changed.append(name)
    return dict(source=str(source),installed=str(installed),changed_bundles=changed,
                added_bundles=sorted(other.keys()-base.keys()),missing_bundles=sorted(base.keys()-other.keys()),
                full_skin_supported=bool(changed) and not (other.keys()-base.keys()),full_skin_status='전체 스킨 실행 중 적용·원복 지원',
                note='디스크 파일끼리 비교한 결과입니다. 실행 중 게임의 모든 자원 상태를 판정하지 않습니다.')

def _style(path):
    from unity_support import unitypy
    UnityPy=unitypy()
    env=UnityPy.load(str(path))
    matches=[]
    for obj in env.objects:
        if obj.type.name!='MonoBehaviour':continue
        data=obj.read_typetree()
        if data.get('m_Name')=='AlwaysAppliedStyleSheet':matches.append((obj,data))
    if len(matches)!=1:raise ValueError('스킨의 공통 스타일을 한 개로 확인하지 못했습니다.')
    obj,data=matches[0]
    def canonical(v):
        if isinstance(v,dict):
            if set(v)=={'m_FileID','m_PathID'}:
                if not v['m_PathID']:return None
                index=v['m_FileID']
                file=obj.assets_file.name if not index else obj.assets_file.externals[index-1].path.replace('\\','/').split('/')[-1]
                return {'file':file,'path':v['m_PathID']}
            return {k:canonical(x) for k,x in v.items()}
        if isinstance(v,(tuple,list)):return [canonical(x) for x in v]
        return v
    return data,canonical(data)

def build_style_patch(source,installed):
    source=normalize_folder(source);installed=normalize_folder(installed)
    raw,canon=_style(source/STYLE_BUNDLE);_,base=_style(installed/STYLE_BUNDLE)
    forbidden=[k for k in base.keys()|canon.keys() if k not in STYLE_FIELDS|{'m_ContentHash'} and base.get(k)!=canon.get(k)]
    if forbidden:raise ValueError('이 스킨은 공통 스타일 외 자원 연결도 달라 부분 적용할 수 없습니다: '+', '.join(sorted(forbidden)))
    if not STYLE_FIELDS<=raw.keys() or any(not isinstance(raw[k],list) for k in STYLE_FIELDS):raise ValueError('공통 스타일 배열의 형식이 올바르지 않습니다.')
    return {k:raw[k] for k in sorted(STYLE_FIELDS)}

class Session:
    def __init__(self,pid):self.pid=pid;self.mutex=None;self.mapping=None;self.ptr=None;self.acquired=False
    def __enter__(self):
        try:
            self.mutex=client.K.CreateMutexW(None,False,f'Local\\FMGraphicsReloadClient1_{self.pid}')
            if not self.mutex:raise C.WinError(C.get_last_error())
            if client.K.WaitForSingleObject(self.mutex,0) not in (0,0x80):raise RuntimeError('다른 새로고침 작업이 실행 중입니다.')
            self.acquired=True;client.install(self.pid)
            self.mapping=client.K.OpenFileMappingW(0xf001f,False,f'Local\\{client.BRIDGE_MAPPING}_{self.pid}')
            if not self.mapping:raise RuntimeError('스킨 연결 모듈을 열지 못했습니다.')
            self.ptr=client.K.MapViewOfFile(self.mapping,0xf001f,0,0,C.sizeof(client.Wire))
            if not self.ptr:raise C.WinError(C.get_last_error())
            self.wire=client.Wire.from_address(self.ptr)
            if self.wire.magic!=0x464d475241504831 or self.wire.version!=1:raise RuntimeError('연결 모듈 버전이 맞지 않습니다.')
            end=time.monotonic()+2
            while not self.wire.heartbeat and time.monotonic()<end:time.sleep(.05)
            if not self.wire.heartbeat:raise RuntimeError('게임 화면의 응답을 확인하지 못했습니다. FM을 재시작한 뒤 사용해 주세요.')
            return self
        except Exception:
            self.__exit__(None,None,None);raise
    def __exit__(self,*args):
        if self.ptr:client.K.UnmapViewOfFile(self.ptr)
        if self.mapping:client.K.CloseHandle(self.mapping)
        if self.acquired:client.K.ReleaseMutex(self.mutex)
        if self.mutex:client.K.CloseHandle(self.mutex)
    def command(self,op,path,index=0):
        w=self.wire
        if w.state in (1,2) or (w.state==4 and w.code==21):raise RuntimeError('이전 요청의 완료를 확인할 수 없습니다. 게임을 재시작한 뒤 사용해 주세요.')
        if len((str(path)+'\0').encode('utf-16-le'))>2048:raise ValueError('작업 폴더 경로가 너무 깁니다.')
        w.path=str(path);w.operation=op;w.code=0;w.completions=index;w.request_token=client.request_token();w.deadline=client.K.GetTickCount64()+120000;w.state=1
        end=time.monotonic()+125
        while w.state in (1,2) and time.monotonic()<end:time.sleep(.05)
        if w.state in (1,2):raise TimeoutError('게임 응답 대기 시간이 지났습니다. 요청을 다시 보내지 말고 완료 여부를 확인해 주세요.')
        if w.state!=3:
            extra={38:'현재 화면의 공통 스타일을 찾지 못했습니다.',42:'이 실행 세션에는 되돌릴 스타일이 없습니다.',43:'불러온 게임이 바뀌어 기존 원복 자료를 사용할 수 없습니다.',45:'적용 오류 후 원복도 확인하지 못했습니다. 게임을 재시작해 주세요.',46:'복사본 검사를 통과하지 못했습니다.',52:'복사본의 원본 복사 검증에 실패했습니다.',53:'복사본 원복 검증에 실패했습니다.',54:'복사본 검사 중 실제 스타일 값이 달라졌습니다.',62:'현재 실행에서 보관 가능한 스킨 자원 수를 초과했습니다. FM을 다시 시작해 주세요.',63:'스킨 자원 수가 지원 범위를 초과했습니다.',64:'게임이 스킨 묶음을 읽지 못했습니다.',77:'이전 스킨 작업이 남아 있거나 이미 같은 상태입니다.',78:'스킨과 원본의 자원 연결 형식이 다릅니다.',79:'게임 자원 목록을 확인하지 못했습니다.',80:'자원 연결에 필요한 함수를 찾지 못했습니다.',81:'교체할 자원 연결이 없습니다.',82:'자원 참조 변경 검사에 실패했습니다.',83:'자원 참조 사전 검사가 완료되지 않았습니다.',84:'스킨 화면의 해상도 설정을 초기화하지 못했습니다.',85:'스킨 메뉴 구조를 안전하게 다시 만들지 못했습니다.'}
            raise RuntimeError(extra.get(w.code,client.ERRORS.get(w.code,f'스킨 작업을 중단했습니다. 오류 {w.code}')))
        return {'operation':op,'matching_styles':w.completions,'panel_reloads':w.panels}

def run_style(pid,source=None,restore=False,progress=lambda s:None):
    import live_skin_guard
    live_skin_guard.require(pid,[STYLE_BUNDLE])
    folder=data_root()/'logs'/'skin_sessions'/uuid.uuid4().hex;folder.mkdir(parents=True)
    if not restore:
        progress('스킨의 공통 스타일과 자원 연결을 확인하고 있습니다…')
        patch=build_style_patch(source,installed_folder(pid))
        patch_path=folder/'style.json';patch_path.write_text(json.dumps(patch,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    with Session(pid) as s:
        if restore:
            progress('이 실행 세션에서 처음 적용하기 전 스타일로 되돌리고 있습니다…')
            result=s.command(12,folder/'unused.json')
        else:
            s.command(14,folder/'unused.json')
            progress('화면에 연결되지 않은 복사본에서 적용·원복을 검사하고 있습니다…')
            s.command(15,patch_path)
            evidence=json.loads(Path(str(patch_path)+'.clone.json').read_text(encoding='utf-8'))
            if any(evidence.get(k)!=v for k,v in patch.items()):raise RuntimeError('복사본의 스타일이 선택한 스킨과 일치하지 않습니다. 실제 적용을 중단했습니다.')
            progress('공통 스타일을 적용하고 화면을 다시 불러오고 있습니다…')
            result=s.command(11,patch_path)
        snapshot=folder/'after.json';s.command(10,snapshot)
        if not restore:
            live=json.loads(snapshot.read_text(encoding='utf-8'))
            if any(live.get(k)!=v for k,v in patch.items()):
                s.command(12,folder/'unused.json');raise RuntimeError('실제 스타일 검증에 실패해 처음 스타일로 되돌렸습니다.')
    return dict(result,pid=pid,scope='common_stylesheet',restored=restore,source=str(source or ''),evidence=str(folder),full_skin_applied=False)
