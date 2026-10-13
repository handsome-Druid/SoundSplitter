from ctypes import (
    POINTER,
    FormatError,
    WinDLL,
    byref,
    c_bool,
    c_int,
    c_ulong,
    c_void_p,
    c_wchar_p,
    get_last_error,
)
from logging import Logger, getLogger
from types import TracebackType
from typing import Self, override

import comtypes
from pycaw.api.audioclient import IAudioClient
from pycaw.constants import DEVICE_STATE, EDataFlow
from pycaw.utils import AudioUtilities
from PySide6.QtCore import (
    QIODevice,
    QMetaObject,
    QMutex,
    QObject,
    Qt,
    QThread,
    Signal,
    Slot,
)
from PySide6.QtMultimedia import QAudioDevice, QAudioFormat, QAudioSink, QAudioSource
from shiboken6 import isValid

from SoundSplitter.external import Config, Split, VolumeMonitor


class Start(QObject):
    finished = Signal(object, object, object)
    _mutex = QMutex()
    _logger: Logger = getLogger(name=__name__)
    _exit_split = Signal(object, object, object)

    class _Thread(QThread):
        @override
        def run(self) -> None:
            avrt = WinDLL(name="avrt", use_last_error=True)
            avrt.AvSetMmThreadCharacteristicsW.restype = c_void_p
            avrt.AvSetMmThreadCharacteristicsW.argtypes = [
                c_wchar_p,
                POINTER(cls=c_ulong),
            ]
            avrt.AvSetMmThreadPriority.restype = c_bool
            avrt.AvSetMmThreadPriority.argtypes = [c_void_p, c_int]
            handle: int | None = avrt.AvSetMmThreadCharacteristicsW(
                "Pro Audio", byref(c_ulong())
            )
            if handle is None:
                error_code: int = get_last_error()
                Split._logger.warning(
                    self.tr(
                        "MMCSS registration failed (Windows error %s: %s); "
                        "the thread will run at normal priority"
                    ),
                    error_code,
                    FormatError(error_code).strip(),
                )
                self._handle = None
            else:
                self._handle = c_void_p(handle)
                if not avrt.AvSetMmThreadPriority(self._handle, 2):
                    error_code: int = get_last_error()
                    Split._logger.warning(
                        self.tr(
                            "Failed to set MMCSS thread priority (Windows error %s: %s)"
                        ),
                        error_code,
                        FormatError(error_code).strip(),
                    )
            try:
                super().run()
            finally:
                if self._handle is not None:
                    avrt.AvRevertMmThreadCharacteristics.restype = c_bool
                    avrt.AvRevertMmThreadCharacteristics.argtypes = [c_void_p]
                    avrt.AvRevertMmThreadCharacteristics(self._handle)

    @override
    def __init__(self, config: Config) -> None:
        super().__init__()
        self._config: Config = config
        self._thread = self._Thread(parent=self)

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
            if hasattr(self, "_thread_conn"):
                self._thread.started.disconnect(self._thread_conn)
                del self._thread_conn
            try:
                if hasattr(self, "_split") and isValid(self._split):
                    if hasattr(self, "_split_conn"):
                        self._split.finished.disconnect(self._split_conn)
                        del self._split_conn
                    if self._split.thread().isCurrentThread():
                        self._split.__exit__(exc_type, exc, tb)
                    else:
                        self._exit_split.emit(exc_type, exc, tb)
            finally:
                if not self._thread.wait(1000):
                    self._thread.quit()
                    self._thread.finished.connect(self._thread.deleteLater)
                    self._logger.warning(
                        msg=self.tr("Failed to clean up the audio thread")
                    )
                    self._thread = self._Thread(parent=self)
                if hasattr(self, "_volume") and isValid(self._volume):
                    try:
                        if hasattr(self, "_volume_conn"):
                            self._volume.finished.disconnect(self._volume_conn)
                            del self._volume_conn
                        self._volume.__exit__(exc_type, exc, tb)
                    finally:
                        self._volume.deleteLater()
        finally:
            if hasattr(self, "_left") and isValid(self._left):
                self._left.stop()
            if hasattr(self, "_right") and isValid(self._right):
                self._right.stop()
            self._mutex.unlock()
            if is_running:
                self.finished.emit(exc_type, exc, tb)

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
            if self._thread.isRunning():
                raise RuntimeError(
                    self.tr("Previous shutdown cleanup is incomplete; retrying cleanup")
                )
            left_device: QAudioDevice | None = self._config.left_device
            right_device: QAudioDevice | None = self._config.right_device
            source_device: QAudioDevice | None = self._config.source_device
            volume_device: QAudioDevice | None = self._config.volume_device
            if left_device is None:
                raise RuntimeError(self.tr("No left channel output selected"))
            if right_device is None:
                raise RuntimeError(self.tr("No right channel output selected"))
            if source_device is None:
                raise RuntimeError(self.tr("No audio input source selected"))
            if left_device == right_device:
                raise RuntimeError(
                    self.tr("Left and right channel outputs cannot use the same device")
                )
            self._left = QAudioSink(left_device)
            self._right = QAudioSink(right_device)
            source = QAudioSource(source_device)
            left_fmt: QAudioFormat = self._left.format()
            right_fmt: QAudioFormat = self._right.format()
            left_sample_rate: int = left_fmt.sampleRate()
            right_sample_rate: int = right_fmt.sampleRate()
            self._left.setBufferFrameCount(
                left_sample_rate * self._config.left_buffer_time_ms // 1000
            )
            self._right.setBufferFrameCount(
                right_sample_rate * self._config.right_buffer_time_ms // 1000
            )
            source.setBufferFrameCount(
                source.format().sampleRate()
                * self._config.source_buffer_time_ms
                // 1000
            )
            left_id: str = bytes(left_device.id().data()).decode()
            right_id: str = bytes(right_device.id().data()).decode()
            source_id: str = bytes(source_device.id().data()).decode()
            min_native_period_us: dict[str, int] = {}
            enumerator = AudioUtilities.GetDeviceEnumerator()
            endpoints = enumerator.EnumAudioEndpoints(  # pyright: ignore[reportAttributeAccessIssue]
                EDataFlow.eAll.value, DEVICE_STATE.ACTIVE.value
            )
            for index in range(endpoints.GetCount()):
                endpoint = endpoints.Item(index)
                endpoint_id: str = endpoint.GetId()
                if endpoint_id not in (left_id, right_id, source_id):
                    continue
                min_native_period_us[endpoint_id] = (
                    endpoint.Activate(IAudioClient._iid_, comtypes.CLSCTX_ALL, None)
                    .QueryInterface(IAudioClient)
                    .GetDevicePeriod()[1]
                    // 10
                )
            if (
                self._config.left_native_period != -1
                and self._config.left_native_period * 1000000 // left_sample_rate
                < min_native_period_us[left_id]
            ):
                raise RuntimeError(
                    self.tr(
                        "The %s native period is too small: %s frames at %s Hz "
                        "lasts %s us, but the device requires at least %s us. "
                        "Choose a larger native period or the default."
                    )
                    % (
                        self.tr("left output"),
                        self._config.left_native_period,
                        left_sample_rate,
                        self._config.left_native_period * 1000000 // left_sample_rate,
                        min_native_period_us[left_id],
                    )
                )
            if (
                self._config.right_native_period != -1
                and self._config.right_native_period * 1000000 // right_sample_rate
                < min_native_period_us[right_id]
            ):
                raise RuntimeError(
                    self.tr(
                        "The %s native period is too small: %s frames at %s Hz "
                        "lasts %s us, but the device requires at least %s us. "
                        "Choose a larger native period or the default."
                    )
                    % (
                        self.tr("right output"),
                        self._config.right_native_period,
                        right_sample_rate,
                        self._config.right_native_period * 1000000 // right_sample_rate,
                        min_native_period_us[right_id],
                    )
                )
            if (
                self._config.source_native_period != -1
                and self._config.source_native_period
                * 1000000
                // source.format().sampleRate()
                < min_native_period_us[source_id]
            ):
                raise RuntimeError(
                    self.tr(
                        "The %s native period is too small: %s frames at %s Hz "
                        "lasts %s us, but the device requires at least %s us. "
                        "Choose a larger native period or the default."
                    )
                    % (
                        self.tr("audio input source"),
                        self._config.source_native_period,
                        source.format().sampleRate(),
                        self._config.source_native_period
                        * 1000000
                        // source.format().sampleRate(),
                        min_native_period_us[source_id],
                    )
                )
            self._left.setNativePeriodFrameCount(self._config.left_native_period)
            self._right.setNativePeriodFrameCount(self._config.right_native_period)
            source.setNativePeriodFrameCount(self._config.source_native_period)
            left_io: QIODevice = self._left.start()
            right_io: QIODevice = self._right.start()
            self._split = Split(
                left_io,
                right_io,
                left_fmt,
                right_fmt,
                source,
                left_latency=self._config.left_latency_ms,
                right_latency=self._config.right_latency_ms,
            )
            self._split_conn: QMetaObject.Connection = self._split.finished.connect(
                self.__exit__
            )
            self._exit_split.connect(
                self._split.__exit__, type=Qt.ConnectionType.QueuedConnection
            )
            left_io.moveToThread(self._thread)
            right_io.moveToThread(self._thread)
            source.moveToThread(self._thread)
            self._split.moveToThread(self._thread)
            self._thread_conn: QMetaObject.Connection = self._thread.started.connect(
                lambda: self._split(None, None, None),
                type=Qt.ConnectionType.DirectConnection,
            )
            self._thread.start()
            if volume_device is not None:
                self._volume = VolumeMonitor(
                    left=self._left,
                    right=self._right,
                    volume_device=volume_device,
                    parent=self,
                )
                self._volume_conn: QMetaObject.Connection = (
                    self._volume.finished.connect(self.__exit__)
                )
                self._volume(None, None, None)
        except BaseException as e:
            self.__exit__(type(e), e, e.__traceback__)
            raise
