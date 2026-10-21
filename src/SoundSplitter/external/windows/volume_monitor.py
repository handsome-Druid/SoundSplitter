from types import TracebackType
from typing import Literal, Self, override

from pycaw.constants import DEVICE_STATE, EDataFlow
from pycaw.utils import AudioDevice, AudioUtilities
from PySide6.QtCore import QMutex, QObject, Qt, Signal, SignalInstance, Slot
from PySide6.QtMultimedia import QAudioDevice

from SoundSplitter.common.volume import VolumeCallback, VolumeObject


class VolumeMonitor(VolumeObject):
    finished = Signal(object, object, object)

    @Slot(object)
    def _on_notify(
        self,
        gain: float | Literal[False],
    ) -> None:
        try:
            self._volume.emit(0.0 if gain is None else gain)
        except BaseException as e:
            self.__exit__(type(e), e, e.__traceback__)
            raise

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
        self._mutex = QMutex()
        self._volume: SignalInstance = volume
        self._device: AudioDevice = next(
            device_
            for device_ in AudioUtilities.GetAllDevices(
                data_flow=EDataFlow.eRender.value,
                device_state=DEVICE_STATE.ACTIVE.value,
            )
            if device_.id == bytes(device.id().data()).decode()
        )
        self.notify.connect(self._on_notify, type=Qt.ConnectionType.QueuedConnection)

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
            if not self._mutex.try_lock():
                return
            try:
                self._callback = VolumeCallback(self)
                self._device.EndpointVolume.RegisterControlChangeNotify(self._callback)
            except BaseException:
                self._mutex.unlock()
                raise
            gain: float = (
                0.0
                if self._device.EndpointVolume.GetMute()
                else float(self._device.EndpointVolume.GetMasterVolumeLevelScalar())
            )
            self._volume.emit(gain)
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
        is_running: bool = not self._mutex.try_lock()
        try:
            if is_running and hasattr(self, "_callback"):
                self._device.EndpointVolume.UnregisterControlChangeNotify(
                    self._callback
                )
        finally:
            self._mutex.unlock()
            if is_running:
                self.finished.emit(exc_type, exc, tb)
