from ctypes import COMError
from types import TracebackType
from typing import Protocol, Self, cast, override

from pycaw.constants import DEVICE_STATE, EDataFlow
from pycaw.pycaw import AudioUtilities
from PySide6.QtCore import QObject

from SoundSplitter.common.volume import VolumeCallback, VolumeObject


class VolumeController(VolumeObject):
    @override
    def __init__(
        self, /, parent: QObject | None = None, *, objectName: str | None = None
    ) -> None:
        super().__init__(parent, objectName=objectName)

    _device: _Device | None = None
    _endpoint_volume: VolumeController._EndpointVolume | None = None

    class _Device(Protocol):
        id: str
        FriendlyName: str
        volume_percent: float = 100.0
        EndpointVolume: VolumeController._EndpointVolume

    class _EndpointVolume(Protocol):
        def UnregisterControlChangeNotify(self, callback: VolumeCallback, /): ...
        def RegisterControlChangeNotify(self, callback: VolumeCallback, /): ...
        def GetMute(self, /) -> int: ...
        def SetMute(self, mute: int, event_context: object, /): ...

    @property
    def device(self) -> str | None:
        return (
            cast(VolumeController._Device, self._device).FriendlyName
            if self._detect()
            else None
        )

    @device.setter
    def device(self, value: str | None) -> None:
        if self._detect():
            try:
                cast(
                    VolumeController._EndpointVolume, self._endpoint_volume
                ).UnregisterControlChangeNotify(self._callback)
            except COMError:
                pass
            self._device = self._endpoint_volume = None
        if value is None:
            return
        self._device = next(
            (
                device
                for device in AudioUtilities.GetAllDevices(
                    data_flow=EDataFlow.eRender.value,
                    device_state=DEVICE_STATE.ACTIVE.value,
                )
                if device.FriendlyName == value
            ),
            None,
        )
        if self._device is None:
            return
        self._endpoint_volume = self._device.EndpointVolume
        self.notify.emit(
            False
            if cast(VolumeController._EndpointVolume, self._endpoint_volume).GetMute()
            == 1
            else cast(VolumeController._Device, self._device).volume_percent / 100.0
        )
        self._callback = VolumeCallback(self)
        cast(
            VolumeController._EndpointVolume, self._endpoint_volume
        ).RegisterControlChangeNotify(self._callback)

    @property
    def volume_percent(self) -> float:
        return (
            cast(VolumeController._Device, self._device).volume_percent
            if self._detect()
            else 100.0
        )

    @volume_percent.setter
    def volume_percent(self, value: float) -> None:
        if not self._detect():
            return
        cast(VolumeController._Device, self._device).volume_percent = value

    @property
    def mute(self) -> bool:
        return (
            cast(VolumeController._EndpointVolume, self._endpoint_volume).GetMute() == 1
            if self._detect()
            else False
        )

    @mute.setter
    def mute(self, value: bool) -> None:
        if self._detect():
            cast(VolumeController._EndpointVolume, self._endpoint_volume).SetMute(
                value, None
            )

    def _detect(self) -> bool:
        if self._device is None:
            return False
        try:
            if (
                AudioUtilities.GetDeviceEnumerator()
                .GetDevice(self._device.id)  # pyright: ignore[reportAttributeAccessIssue]
                .GetState()
                == DEVICE_STATE.ACTIVE.value
            ):
                return True
            else:
                if hasattr(self, "_callback"):
                    try:
                        cast(
                            VolumeController._EndpointVolume, self._endpoint_volume
                        ).UnregisterControlChangeNotify(self._callback)
                    except COMError:
                        pass
                self._device = self._endpoint_volume = None
                return False
        except COMError:
            if hasattr(self, "_callback"):
                try:
                    cast(
                        VolumeController._EndpointVolume, self._endpoint_volume
                    ).UnregisterControlChangeNotify(self._callback)
                except COMError:
                    pass
            self._device = self._endpoint_volume = None
            return False

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
        /,
    ) -> None:
        if self._detect() and hasattr(self, "_callback"):
            try:
                cast(
                    VolumeController._EndpointVolume, self._endpoint_volume
                ).UnregisterControlChangeNotify(self._callback)
            except COMError:
                pass
            self._device = self._endpoint_volume = None
