import json
from types import TracebackType
from typing import Self, override

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal, Slot


class VolumeController(QObject):
    notify = Signal(object)
    _device: str | None = None
    _name: str | None = None
    _volume_percent: float = 100.0
    _mute: bool = False

    @override
    def __init__(
        self, /, parent: QObject | None = None, *, objectName: str | None = None
    ) -> None:
        super().__init__(parent, objectName=objectName)
        self._subscription = QProcess(self)
        self._subscription.setProgram("pactl")
        self._subscription.setArguments(["subscribe"])
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("LC_ALL", "C")
        self._subscription.setProcessEnvironment(environment)
        self._subscription.readyReadStandardOutput.connect(self._on_change)

    @property
    def device(self) -> str | None:
        self._refresh()
        return self._device

    @device.setter
    def device(self, value: str | None) -> None:
        if self._subscription.state() != QProcess.ProcessState.NotRunning:
            self._subscription.kill()
            self._subscription.waitForFinished()
        self._device = value
        self._name = None
        if value is not None:
            self._refresh()
            if self._device is not None:
                self._subscription.start()
                if not self._subscription.waitForStarted():
                    raise RuntimeError(self._subscription.errorString())

    @property
    def volume_percent(self) -> float:
        self._refresh()
        return self._volume_percent

    @volume_percent.setter
    def volume_percent(self, value: float) -> None:
        self._refresh()
        if self._name is None:
            return
        process = QProcess(self)
        try:
            process.start("pactl", ["set-sink-volume", self._name, f"{value}%"])
            if not process.waitForFinished() or process.exitCode() != 0:
                raise RuntimeError(
                    bytes(process.readAllStandardError().data()).decode()
                    or process.errorString()
                )
        finally:
            process.deleteLater()
        self._refresh()

    @property
    def mute(self) -> bool:
        self._refresh()
        return self._mute

    @mute.setter
    def mute(self, value: bool) -> None:
        self._refresh()
        if self._name is None:
            return
        process = QProcess(self)
        try:
            process.start("pactl", ["set-sink-mute", self._name, "1" if value else "0"])
            if not process.waitForFinished() or process.exitCode() != 0:
                raise RuntimeError(
                    bytes(process.readAllStandardError().data()).decode()
                    or process.errorString()
                )
        finally:
            process.deleteLater()
        self._refresh()

    @Slot()
    def _on_change(self) -> None:
        changed = False
        while self._subscription.canReadLine():
            event = bytes(self._subscription.readLine().data()).decode()
            if " on sink #" in event:
                changed = True
        if changed:
            self._refresh()

    @Slot()
    def _refresh(self) -> None:
        if self._device is None:
            return
        process = QProcess(self)
        try:
            process.start("pactl", ["--format=json", "list", "sinks"])
            if not process.waitForFinished() or process.exitCode() != 0:
                raise RuntimeError(
                    bytes(process.readAllStandardError().data()).decode()
                    or process.errorString()
                )
            endpoints = json.loads(
                bytes(process.readAllStandardOutput().data()).decode()
            )
        finally:
            process.deleteLater()
        endpoint = next(
            (item for item in endpoints if item["description"] == self._device), None
        )
        previous = (self._name, self._volume_percent, self._mute)
        if endpoint is None:
            self._device = self._name = None
            self._volume_percent = 100.0
            self._mute = False
        else:
            self._name = endpoint["name"]
            self._volume_percent = (
                max(channel["value"] for channel in endpoint["volume"].values())
                / 65536
                * 100
            )
            self._mute = endpoint["mute"]
        if previous != (self._name, self._volume_percent, self._mute):
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
