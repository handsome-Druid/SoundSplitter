from sys import platform

if platform == "win32":
    import comtypes  # noqa: F401

from .config import Config as Config
from .split import Split as Split

if platform == "linux":
    from .linux.alsa import ALSA as ALSA
    from .linux.volume_controller import VolumeController as VolumeController
    from .linux.volume_monitor import VolumeMonitor as VolumeMonitor

if platform == "win32":
    from .windows.volume_controller import VolumeController as VolumeController
    from .windows.volume_monitor import VolumeMonitor as VolumeMonitor
