"""Read bundled resources and retain injected DLLs beyond onefile extraction."""
import hashlib
import os
from pathlib import Path
import sys
import tempfile
from app_storage import data_root


ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))


def resource(relative):
    return ROOT / relative


def runtime_dll(name):
    source = resource('runtime') / name
    payload = source.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    folder = data_root() / 'runtime' / digest
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name
    if target.exists():
        if target.read_bytes() != payload:
            raise RuntimeError('연결 모듈 보관 파일이 손상되었습니다: ' + str(target))
        return target.resolve()
    fd, temporary = tempfile.mkstemp(prefix='bridge-', suffix='.tmp', dir=folder)
    temporary = Path(temporary)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            # On Windows rename fails if another instance already installed it.
            temporary.rename(target)
        except FileExistsError:
            if target.read_bytes() != payload:
                raise RuntimeError('연결 모듈 보관 파일이 손상되었습니다: ' + str(target))
    finally:
        temporary.unlink(missing_ok=True)
    return target.resolve()
