"""Bundle I/O does not require UnityPy's optional proprietary audio decoder."""
import importlib
import sys
import types


def unsupported_audio(*args, **kwargs):
    raise NotImplementedError('Audio conversion is not included in FM Graphics Reload.')


def unitypy():
    # UnityPy eagerly imports AudioClipConverter, even for bundle metadata I/O.
    # Supply only its unused decoder entry point; never load/download FMOD.
    if 'fmod_toolkit' not in sys.modules:
        audio = types.ModuleType('fmod_toolkit')
        audio.raw_to_wav = unsupported_audio
        sys.modules['fmod_toolkit'] = audio
    return importlib.import_module('UnityPy')
