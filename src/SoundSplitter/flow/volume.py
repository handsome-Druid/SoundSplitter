from types import TracebackType
from typing import Self, override

from PySide6.QtCore import QObject, Signal

from SoundSplitter.external.volume_controller import VolumeController


class Volume(QObject):
    left_notify = Signal(object)
    right_notify = Signal(object)

    @override
    def __init__(
        self, /, parent: QObject | None = None, *, objectName: str | None = None
    ) -> None:
        super().__init__(parent, objectName=objectName)
        self._left_controller = VolumeController(parent=self)
        self._left_controller.notify.connect(self.left_notify.emit)
        self._right_controller = VolumeController(parent=self)
        self._right_controller.notify.connect(self.right_notify.emit)

    @property
    def left(self) -> str | None:
        return self._left_controller.device

    @left.setter
    def left(self, value: str) -> None:
        self._left_controller.device = value

    @property
    def left_volume_percent(self) -> float:
        return self._left_controller.volume_percent

    @left_volume_percent.setter
    def left_volume_percent(self, value: float) -> None:
        self._left_controller.volume_percent = value

    @property
    def left_mute(self) -> bool:
        return self._left_controller.mute

    @left_mute.setter
    def left_mute(self, value: bool) -> None:
        self._left_controller.mute = value

    @property
    def right(self) -> str | None:
        return self._right_controller.device

    @right.setter
    def right(self, value: str) -> None:
        self._right_controller.device = value

    @property
    def right_volume_percent(self) -> float:
        return self._right_controller.volume_percent

    @right_volume_percent.setter
    def right_volume_percent(self, value: float) -> None:
        self._right_controller.volume_percent = value

    @property
    def right_mute(self) -> bool:
        return self._right_controller.mute

    @right_mute.setter
    def right_mute(self, value: bool) -> None:
        self._right_controller.mute = value

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
        /,
    ) -> None:
        try:
            self._left_controller.__exit__(exc_type, exc, tb)
        finally:
            self._right_controller.__exit__(exc_type, exc, tb)
