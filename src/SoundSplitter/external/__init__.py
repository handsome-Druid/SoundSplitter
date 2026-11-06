from sys import platform

if platform == "win32":
    import comtypes  # pyright: ignore[reportMissingImports] # noqa: F401
from .config import Config as Config

if platform == "linux":
    from .linux import *
if platform == "win32":
    from .windows import *
__all__: list[str] = ["Config", "Split", "VolumeController", "VolumeMonitor"]
