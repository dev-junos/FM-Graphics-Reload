"""Collect installed dependency notices without running the application."""
from importlib import metadata
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
parts = ['FM Graphics Reload — third-party notices\n\n'
         'Application code: MIT, Copyright (c) 2026 JunHo.\n'
         'Third-party components retain their own licenses below.\n'
         'FM game files, user skins, and the FMOD audio SDK are not included.\n']
seen = set()


def append(title, path):
    path = Path(path)
    content = path.read_text(encoding='utf-8', errors='replace')
    key = (title, content)
    if key not in seen:
        seen.add(key)
        parts.append('\n' + '=' * 72 + '\n' + title + '\n' + '=' * 72 + '\n' + content)


for line in (ROOT / 'requirements-build.txt').read_text().splitlines():
    if not line or line.startswith('#'):
        continue
    name = line.split('==')[0]
    dist = metadata.distribution(name)
    parts.append(f'\n{name} {dist.version}\n')
    found = False
    for entry in dist.files or []:
        filename = Path(str(entry)).name.lower()
        if filename.startswith(('license', 'copying', 'notice')):
            path = Path(dist.locate_file(entry))
            if path.is_file():
                append(name + ': ' + str(entry), path)
                found = True
    if not found:
        raise RuntimeError('No license file found for ' + name)

append('MinHook (including Hacker Disassembler Engine)', ROOT / 'vendor/minhook/LICENSE.txt')
append('CPython and bundled components', Path(sys.base_prefix) / 'LICENSE.txt')
for path in sorted((ROOT / 'packaging/licenses').glob('*.txt')):
    append(path.stem, path)
output = ROOT / 'THIRD_PARTY_NOTICES.txt'
output.write_text('\n'.join(parts) + '\n', encoding='utf-8')
print(f'Collected notices: {output.name} ({output.stat().st_size} bytes)')
