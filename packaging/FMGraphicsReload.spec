"""Onefile distribution; no user data, skins or proprietary FMOD binary."""
from pathlib import Path
import runpy
from PyInstaller.utils.hooks import collect_all
from PyInstaller.utils.hooks.tcl_tk import tcltk_info

if not tcltk_info.available or tcltk_info.tcl_data_missing or tcltk_info.tk_data_missing:
    raise RuntimeError('A working Tcl/Tk runtime is required; refusing to omit tkinter.')

root = Path(SPECPATH).parent
version = runpy.run_path(str(root / 'app/version.py'))['VERSION']
data, binaries, hidden = collect_all('UnityPy', filter_submodules=lambda name: name != 'UnityPy.__main__' and not name.startswith('UnityPy.tools'))
data += [(str(root / name), '.') for name in ('LICENSE', 'THIRD_PARTY_NOTICES.txt', '사용 안내.md')]
data += [(str(root / 'assets/app.ico'), 'assets'),
         (str(root / 'runtime/profile.json'), 'runtime')]
data += [(str(root / f'assets/icon-{n}.png'), 'assets') for n in (256, 512, 1024)]
# An unfinished donation configuration never adds a broken menu to a release.
import json
donation_config=root / 'assets/donation.json'
if donation_config.is_file() and json.loads(donation_config.read_text(encoding='utf-8')).get('url'):
    qr=root / 'assets/donation-qr.png'
    if not qr.is_file():raise RuntimeError('Donation URL configured without its QR image.')
    data += [(str(donation_config),'assets'),(str(qr),'assets')]
binaries += [(str(root / 'runtime/fm_skin_theme_probe_v10.dll'), 'runtime')]
a = Analysis([str(root / 'app/main.py')], pathex=[str(root / 'app')],
             binaries=binaries, datas=data, hiddenimports=hidden,
             hookspath=[], runtime_hooks=[],
             excludes=['fmod_toolkit', 'pyfmodex', 'numpy', 'requests', 'urllib3',
                       'cryptography', 'certifi', 'chardet', 'charset_normalizer',
                       'setuptools', 'pip', 'pytest'], noarchive=False)

# UnityPy's optional audio conversion dependency is not used by this app.
# unity_support supplies the unused decoder API without the proprietary SDK.
def distributable(entry):
    name = entry[0].replace('\\', '/').lower()
    return '/libfmod/' not in '/' + name and Path(name).name not in ('fmod.dll', 'fmodl.dll', 'libfmod.so', 'libfmod.dylib')

a.binaries = [entry for entry in a.binaries if distributable(entry)]
a.datas = [entry for entry in a.datas if distributable(entry)]
for entry in a.binaries + a.datas:
    if entry[0].lower().endswith('.bundle'):
        raise RuntimeError('Skin bundles must not be distributed.')
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [],
          name='FM Graphics Reload ' + version, debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False,
          icon=str(root / 'assets/app.ico'))
