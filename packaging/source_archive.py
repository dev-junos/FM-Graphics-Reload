"""Create a source-only release from an explicit allowlist, never app data."""
from pathlib import Path
import runpy
import zipfile

root = Path(__file__).resolve().parents[1]
version = runpy.run_path(str(root / 'app/version.py'))['VERSION']
files = [root / name for name in (
    '.gitignore', '.gitattributes', 'LICENSE', 'README.md', 'CHANGELOG.md', '사용 안내.md',
    'THIRD_PARTY_NOTICES.txt', 'requirements-build.txt', 'build.ps1', 'runtime/profile.json')]
for folder, pattern in [('app', '*.py'), ('native', '*.c'), ('native', '*.h'),
                        ('tests', '*.py'), ('tests', '*.c'),
                        ('assets', '*.png'), ('assets', '*.ico'), ('assets', '*.md'), ('assets', '*.json'),
                        ('packaging', '*.py'), ('packaging', '*.spec')]:
    files.extend((root / folder).glob(pattern))
files.extend((root / 'packaging/licenses').glob('*.txt'))
for path in (root / 'vendor/minhook').rglob('*'):
    if path.is_file() and (path.suffix in ('.c', '.h') or path.name == 'LICENSE.txt'):
        files.append(path)
output = root / ('dist-' + version) / ('FM Graphics Reload ' + version + ' source.zip')
output.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in sorted(set(files)):
        if not path.is_file() or path.is_symlink():
            raise RuntimeError('Source file unavailable: ' + str(path))
        archive.write(path, path.relative_to(root).as_posix())
print(f'Source archive: {output.name} ({len(set(files))} files)')
