from types import TracebackType
from typing import Literal, Self, override

from pulsectl import PulseDisconnected, PulseError
from PySide6.QtCore import QObject, Signal, SignalInstance, Slot
from PySide6.QtMultimedia import QAudioDevice

from .volume_controller import VolumeController


class VolumeMonitor(VolumeController):
    finished = Signal(object, object, object)
    _running: bool = False

    @override
    def __init__(
        self,
        volume: SignalInstance,
        device: QAudioDevice,
        /,
        parent: QObject | None = None,
        *,
        objectName: str | None = None,
    ) -> None:
        super().__init__(parent, objectName=objectName)
        self._volume = volume
        self._description = device.description()
        self.notify.connect(self._on_notify)

    @Slot(object)
    def _on_notify(self, gain: float | Literal[False]) -> None:
        self._volume.emit(0.0 if gain is False else gain)

    @Slot(object, object, object)
    def __call__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
        /,
    ) -> None:
        if exc_type is not None:
            self.__exit__(exc_type, exc, tb)
            return
        if self._running:
            return
        self._running = True
        try:
            self.device = self._description
            if self.device is None:
                raise RuntimeError(f"Audio output not found: {self._description}")
            self._volume.emit(0.0 if self.mute else self.volume_percent / 100)
        except (
            OSError,
            ValueError,
            RuntimeError,
            PulseError,
            PulseDisconnected,
        ) as error:
            self.__exit__(type(error), error, error.__traceback__)
            raise

    def __enter__(self) -> Self:
        return self

    @Slot(object, object, object)
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
        /,
    ) -> None:
        running = self._running
        self._running = False
        super().__exit__(exc_type, exc, tb)
        if running:
            self.finished.emit(exc_type, exc, tb)
