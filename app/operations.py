from app_storage import data_root
import json
from pathlib import Path
import time
from client import ROOT, fm_pids, request, validate_folder

def run(folder='',preflight=False,progress=lambda s:None):
    pids=fm_pids()
    if len(pids)!=1: raise RuntimeError('FM26을 한 개 실행하고 저장된 게임을 불러와 주세요.')
    details={}
    if not preflight:
        progress('그래픽 폴더와 config.xml을 확인하고 있습니다…')
        folder,configs,mappings=validate_folder(folder)
        details=dict(config_files=configs,mappings=mappings)
    start=time.monotonic()
    result=request(pids[0],folder,preflight,progress)
    result.update(details,elapsed_seconds=round(time.monotonic()-start,2))
    return result

def save_log(value):
    logs=data_root()/'logs'; logs.mkdir(parents=True,exist_ok=True)
    target=logs/(time.strftime('%Y%m%d_%H%M%S')+f'_{time.time_ns()%1000000:06d}.json')
    target.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

