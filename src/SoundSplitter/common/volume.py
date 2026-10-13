from typing import override

from pycaw.callbacks import AudioEndpointVolumeCallback
from PySide6.QtCore import QObject, Signal


class VolumeObject(QObject):
    notify = Signal(object)

    @override
    def __init__(
        self, /, parent: QObject | None = None, *, objectName: str | None = None
    ) -> None:
        super().__init__(parent, objectName=objectName)


class VolumeCallback(AudioEndpointVolumeCallback):
    @override
    def __init__(self, parent: VolumeObject, /) -> None:
        super().__init__()
        self._parent: VolumeObject = parent

    @override
    def on_notify(
        self,
        new_volume: float,
        new_mute: int,
        event_context: object,
        channels: int,
        channel_volumes: list[float],
    ) -> None:
        self._parent.notify.emit(False if new_mute == 1 else new_volume)
