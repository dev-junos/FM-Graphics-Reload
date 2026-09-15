"""User-owned data lives separately from the installed application."""
import os
from pathlib import Path


def data_root():
    local=os.environ.get('LOCALAPPDATA')
    return (Path(local) if local else Path.home()/'AppData'/'Local')/'FM Graphics Reload'


def skin_root():
    return data_root()/'skins'
