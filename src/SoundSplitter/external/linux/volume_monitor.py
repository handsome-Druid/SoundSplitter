from math import ceil
from select import POLLIN, POLLOUT, poll
from types import TracebackType
from typing import Self, override

from pulsectl import Pulse
from PySide6.QtCore import (
    QObject,
    QSocketNotifier,
    QTimer,
    Signal,
    SignalInstance,
    Slot,
)
from PySide6.QtMultimedia import QAudioDevice


class VolumeMonitor(QObject):
    finished = Signal(object, object, object)
    _pulse: Pulse | None = None
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
        self._notifiers: list[QSocketNotifier] = []

    def _poll(self, fds, timeout):
        for notifier in self._notifiers:
            notifier.setEnabled(False)
            notifier.deleteLater()
        self._notifiers.clear()
        pending = poll()
        for fd in fds:
            pending.register(fd.fd, fd.events)
            for mask, kind in (
                (POLLIN, QSocketNotifier.Type.Read),
                (POLLOUT, QSocketNotifier.Type.Write),
            ):
                if fd.events & mask:
                    notifier = QSocketNotifier(fd.fd, kind, self)
                    notifier.activated.connect(self._on_change)
                    self._notifiers.append(notifier)
        ready = dict(pending.poll(None if timeout < 0 else ceil(timeout * 1000)))
        for fd in fds:
            fd.revents = ready.get(fd.fd, 0)
        return len(ready)

    @Slot()
    def _on_change(self) -> None:
        try:
            if self._pulse is not None:
                self._pulse.event_listen(timeout=0.001)
        except BaseException as e:
            self.__exit__(type(e), e, e.__traceback__)
            raise

    @Slot()
    def _on_notify(self) -> None:
        if self._pulse is None:
            return
        try:
            sink = next(
                item for item in self._pulse.sink_list() if item.index == self._index
            )
            self._volume.emit(0.0 if sink.mute else max(sink.volume.values))
        except BaseException as e:
            self.__exit__(type(e), e, e.__traceback__)
            raise

    @Slot(object, object, object)
    def __call__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
        /,
    ) -> None:
        try:
            if exc_type is not None:
                self.__exit__(exc_type, exc, tb)
                return
            if self._running:
                return
            self._running = True
            self._pulse = Pulse("SoundSplitter volume monitor")
            self._pulse.set_poll_func(self._poll)
            self._pulse.event_callback_set(
                lambda event: QTimer.singleShot(0, self, self._on_notify)
            )
            self._pulse.event_mask_set("sink")
            sink = next(
                (
                    item
                    for item in self._pulse.sink_list()
                    if item.description == self._description
                ),
                None,
            )
            if sink is None:
                raise RuntimeError(f"Audio output not found: {self._description}")
            self._index: int = sink.index
            self._volume.emit(0.0 if sink.mute else max(sink.volume.values))
        except BaseException as e:
            self.__exit__(type(e), e, e.__traceback__)
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
        try:
            for notifier in self._notifiers:
                notifier.setEnabled(False)
                notifier.deleteLater()
            self._notifiers.clear()
            if self._pulse is not None:
                self._pulse.close()
                self._pulse = None
        finally:
            if running:
                self.finished.emit(exc_type, exc, tb)
