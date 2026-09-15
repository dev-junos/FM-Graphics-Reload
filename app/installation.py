"""Locate actual FM installation folders without depending on a shipped skin."""
from pathlib import Path
import os
import re
import winreg
import client
import skins

RELATIVE=Path('fm_Data/StreamingAssets/aa/StandaloneWindows64')


def validate(value):
    folder=Path(value).expanduser().resolve(strict=True)
    if folder.name.lower()=='fm.exe':folder=folder.parent
    if folder.name.lower()=='standalonewindows64':folder=folder.parents[3]
    if not (folder/'fm.exe').is_file():raise ValueError('fm.exe가 들어 있는 FM26 설치 폴더를 선택해 주세요.')
    skins.normalize_folder(folder/RELATIVE)
    return folder


def locate(data,pid=None):
    if pid is not None:return skins.normalize_folder(skins.installed_folder(pid))
    pids=client.fm_pids()
    if len(pids)==1:
        try:return skins.normalize_folder(skins.installed_folder(pids[0]))
        except OSError:pass
    if data.get('game_folder'):
        try:return validate(data['game_folder'])/RELATIVE
        except (OSError,ValueError):pass
    roots=[]
    for hive,key,name in [(winreg.HKEY_CURRENT_USER,r'Software\Valve\Steam','SteamPath'),(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\WOW6432Node\Valve\Steam','InstallPath')]:
        try:
            with winreg.OpenKey(hive,key) as handle:roots.append(Path(winreg.QueryValueEx(handle,name)[0]))
        except OSError:pass
    program_files=os.environ.get('ProgramFiles(x86)')
    if program_files:roots.append(Path(program_files)/'Steam')
    libraries=list(roots)
    for root in roots:
        config=root/'steamapps/libraryfolders.vdf'
        try:raw=config.read_text(encoding='utf-8')
        except OSError:continue
        libraries.extend(Path(p.replace('\\\\','\\')) for p in re.findall(r'"path"\s+"([^"]+)"',raw,re.I))
    for root in dict.fromkeys(libraries):
        try:return validate(root/'steamapps/common/Football Manager 26')/RELATIVE
        except (OSError,ValueError):pass
    raise ValueError('FM26 설치 폴더를 찾지 못했습니다. 게임 설치 폴더 행의 「선택」으로 지정해 주세요.')
