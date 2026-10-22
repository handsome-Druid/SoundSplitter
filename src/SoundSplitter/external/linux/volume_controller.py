from types import TracebackType
from typing import Protocol, Self, cast, override

from pulsectl import Pulse, PulseDisconnected, PulseError, PulseVolumeInfo
from PySide6.QtCore import QObject, QTimer, Signal, Slot


class VolumeController(QObject):
    class _Sink(Protocol):
        index: int
        name: str
        volume: PulseVolumeInfo

    notify = Signal(object)
    _device: str | None = None
    _pulse: Pulse | None = None
    _sink: _Sink | None = None
    _volume_percent: float = 100.0
    _mute: bool = False
    _changed: bool = False

    @override
    def __init__(
        self, /, parent: QObject | None = None, *, objectName: str | None = None
    ) -> None:
        super().__init__(parent, objectName=objectName)
        self._subscription = QTimer(self, interval=50)
        self._subscription.timeout.connect(self._on_change)

    @property
    def device(self) -> str | None:
        self._refresh()
        return self._device

    @device.setter
    def device(self, value: str | None) -> None:
        self._subscription.stop()
        if self._pulse is not None:
            self._pulse.close()
            self._pulse = None
        self._device = value
        self._sink = None
        self._volume_percent = 100.0
        self._mute = False
        self._changed = False
        if value is not None:
            try:
                self._pulse = Pulse("SoundSplitter volume")
                self._pulse.event_callback_set(
                    lambda event: setattr(self, "_changed", True)
                )
                self._pulse.event_mask_set("sink")
                self._refresh()
                if self._device is not None:
                    self._subscription.start()
            except PulseError, PulseDisconnected:
                self.device = None
                raise

    @property
    def volume_percent(self) -> float:
        self._refresh()
        return self._volume_percent

    @volume_percent.setter
    def volume_percent(self, value: float) -> None:
        self._refresh()
        if self._pulse is None or self._sink is None:
            return
        volumes = self._sink.volume
        channels = cast(list[float], volumes.values)
        maximum = max(channels)
        volumes.values = [
            channel / maximum * value / 100 if maximum else value / 100
            for channel in channels
        ]
        self._pulse.sink_volume_set(self._sink.index, volumes)
        self._refresh()

    @property
    def mute(self) -> bool:
        self._refresh()
        return self._mute

    @mute.setter
    def mute(self, value: bool) -> None:
        self._refresh()
        if self._pulse is None or self._sink is None:
            return
        self._pulse.sink_mute(self._sink.index, value)
        self._refresh()

    @Slot()
    def _on_change(self) -> None:
        if self._pulse is None:
            return
        try:
            # Dispatch subscription events before making synchronous queries.
            self._pulse.event_listen(timeout=0.001)
            if self._changed:
                self._changed = False
                self._refresh()
        except PulseError, PulseDisconnected:
            self.device = None
            raise

    @Slot()
    def _refresh(self) -> None:
        if self._pulse is None or self._device is None:
            return
        endpoint = next(
            (
                item
                for item in self._pulse.sink_list()
                if item.description == self._device
            ),
            None,
        )
        previous = (self._sink and self._sink.name, self._volume_percent, self._mute)
        if endpoint is None:
            self.device = None
        else:
            self._sink = endpoint
            self._volume_percent = max(endpoint.volume.values) * 100
            self._mute = bool(endpoint.mute)
        if previous != (
            self._sink and self._sink.name,
            self._volume_percent,
            self._mute,
        ):
            self.notify.emit(False if self._mute else self._volume_percent / 100)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
        /,
    ) -> None:
        self.device = None
