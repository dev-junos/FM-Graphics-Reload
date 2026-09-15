"""User-requested baseline adoption and disposable app-cache cleanup, offline only."""
import os
from pathlib import Path
import shutil
import uuid
from app_storage import data_root
import installed_skins
import installation
import skin_library


def adopt_current(data,progress=lambda s:None):
    installed_skins.ensure_process(None)
    installed=installation.locate(data)
    with installed_skins.lock(installed):
        root=installed_skins.root_for(installed)
        if (root/'pending.json').exists():
            raise ValueError('중단된 설치 파일 작업을 먼저 복구해야 합니다. FM 종료 후 ON/OFF를 다시 시도해 주세요.')
        old=installed_skins.read_state(installed)
        transaction=uuid.uuid4().hex
        progress('현재 설치 파일을 새 스킨 기준으로 등록합니다…')
        installed_skins.atomic_json(root/'history'/(transaction+'.json'),old)
        installed_skins.ensure_process(None)
        # Disable selections first: a failed state write cannot auto-apply an old ON list.
        for item in data['skins']:item['enabled']=False
        data['disk_pending']=False;skin_library.save(data)
        installed_skins.atomic_json(root/'state.json',dict(version=1,installed=str(installed),files={},transaction=transaction))
    return dict(installed=str(installed),backup_history=str(root/'history'),files_unchanged=True)


def clear_cache(progress=lambda s:None):
    installed_skins.ensure_process(None)
    root=data_root().resolve()
    targets=[root/'cache',root/'logs'/'full_skin',root/'logs'/'skin_sessions',root/'logs'/'live_inventory']
    # Validate every target and descendant before deleting any tree.
    for target in targets:
        for parent in (target,*target.parents):
            if parent==root:break
            if parent.is_symlink() or parent.is_junction():raise ValueError('연결된 캐시 경로는 초기화할 수 없습니다.')
        resolved=target.resolve()
        if not resolved.is_relative_to(root) or resolved==root:raise ValueError('캐시 경로가 프로그램 저장 폴더 밖입니다.')
        if target.exists():
            if not target.is_dir():raise ValueError('캐시 경로가 폴더가 아닙니다: '+str(target))
            for directory,dirs,files in os.walk(target,followlinks=False):
                for name in dirs+files:
                    path=Path(directory)/name
                    if path.is_symlink() or path.is_junction():raise ValueError('캐시에 연결 파일이 있어 초기화를 중단했습니다.')
    removed=[]
    for target in targets:
        installed_skins.ensure_process(None)
        if target.exists():
            progress('프로그램의 임시 스킨 캐시를 지우고 있습니다…')
            shutil.rmtree(target);removed.append(str(target))
    return dict(removed=removed,backups_preserved=True,skins_preserved=True)
