#  pyright: reportAttributeAccessIssue=false
from logging import Logger, getLogger
from sys import platform
from types import TracebackType
from typing import Self, override

from PySide6.QtCore import (
    QMetaObject,
    QMutex,
    QObject,
    Qt,
    QThread,
    Signal,
    Slot,
)
from shiboken6 import isValid

from SoundSplitter.external import Config, Split, VolumeMonitor
from SoundSplitter.external.config import QAudioDevice


class Start(QObject):
    finished = Signal(object, object, object)
    _logger: Logger = getLogger(name=__name__)
    _exit_split = Signal(object, object, object)

    class _Thread(QThread):
        if platform == "win32":

            @override
            def run(self) -> None:
                from ctypes import (
                    POINTER,
                    FormatError,
                    WinDLL,
                    byref,
                    c_bool,
                    c_ulong,
                    c_void_p,
                    c_wchar_p,
                    get_last_error,
                )

                avrt = WinDLL(name="avrt", use_last_error=True)
                avrt.AvSetMmThreadCharacteristicsW.restype = c_void_p
                avrt.AvSetMmThreadCharacteristicsW.argtypes = [
                    c_wchar_p,
                    POINTER(cls=c_ulong),
                ]
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
                try:
                    super().run()
                finally:
                    if handle is not None:
                        avrt.AvRevertMmThreadCharacteristics.restype = c_bool
                        avrt.AvRevertMmThreadCharacteristics.argtypes = [c_void_p]
                        avrt.AvRevertMmThreadCharacteristics(c_void_p(handle))
        elif platform == "linux":

            @override
            def run(self) -> None:
                from resource import (
                    RLIM_INFINITY,
                    RLIMIT_RTTIME,
                    getrlimit,
                    setrlimit,
                )
                from threading import get_native_id

                from PySide6.QtCore import Q_ARG
                from PySide6.QtDBus import (
                    QDBusConnection,
                    QDBusInterface,
                    QDBusMessage,
                    QDBusVariant,
                )

                service = "org.freedesktop.RealtimeKit1"
                path = "/org/freedesktop/RealtimeKit1"
                bus: QDBusConnection = QDBusConnection.systemBus()
                properties = QDBusInterface(
                    service,
                    path,
                    interface="org.freedesktop.DBus.Properties",
                    connection=bus,
                )
                reply: QDBusMessage = properties.call("Get", service, "RTTimeUSecMax")
                error: str | None = None
                if reply.type() == QDBusMessage.MessageType.ErrorMessage:
                    error = reply.errorMessage()
                else:
                    value = reply.arguments()[0]
                    if isinstance(value, QDBusVariant):
                        value = value.variant()
                    maximum = int(value)
                    soft, hard = getrlimit(RLIMIT_RTTIME)
                    if hard == RLIM_INFINITY or hard > maximum:
                        error = (
                            f"RLIMIT_RTTIME hard limit {hard} exceeds RTKit maximum "
                            f"{maximum}; refusing to lower the hard limit without "
                            "explicit consent"
                        )
                    else:
                        limit = hard if soft == RLIM_INFINITY else min(soft, hard)
                        try:
                            if limit != soft:
                                setrlimit(RLIMIT_RTTIME, (limit, hard))
                        except (OSError, ValueError) as exc:
                            error = str(object=exc)
                        else:
                            rtkit = QDBusInterface(
                                service, path, interface=service, connection=bus
                            )
                            if not rtkit.isValid():
                                error = rtkit.lastError().message()
                            else:
                                try:
                                    invoked = QMetaObject.invokeMethod(
                                        rtkit,
                                        "MakeThreadRealtime",
                                        Qt.ConnectionType.DirectConnection,
                                        Q_ARG("qulonglong", get_native_id()),
                                        Q_ARG("uint", 5),
                                    )
                                except RuntimeError as exc:
                                    error = str(object=exc)
                                else:
                                    if rtkit.lastError().isValid():
                                        error = rtkit.lastError().message()
                                    elif not invoked:
                                        error = "Could not invoke MakeThreadRealtime"
                if error is not None:
                    Start._logger.warning(
                        "RTKit realtime scheduling failed; "
                        "the audio thread will run at normal priority: %s",
                        error,
                    )

                super().run()

    @override
    def __init__(self, config: Config) -> None:
        super().__init__()
        self._config: Config = config
        self._mutex = QMutex()
        self._thread = self._Thread(parent=self)
        if platform == "linux":
            from SoundSplitter.external import ALSA

            self._alsa = ALSA()

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
            self._thread.requestInterruption()
            if hasattr(self, "_thread_conn"):
                self._thread.started.disconnect(self._thread_conn)
                del self._thread_conn
            try:
                if hasattr(self, "_split") and isValid(self._split):
                    if hasattr(self, "_split_conn"):
                        self._split.finished.disconnect(self._split_conn)
                        del self._split_conn
                    self._split.__exit__(exc_type, exc, tb)
            finally:
                self._thread.quit()
                if not self._thread.wait(1000):
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
                if hasattr(self, "_alsa"):
                    self._alsa.__exit__(exc_type, exc, tb)
        finally:
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
            if hasattr(self, "_alsa"):
                if self._config.left is None:
                    raise RuntimeError(self.tr("No left channel output selected"))
                if self._config.right is None:
                    raise RuntimeError(self.tr("No right channel output selected"))
                if self._config.source is None:
                    raise RuntimeError(self.tr("No audio input source selected"))
                self._alsa(self._config.left)
                self._alsa(self._config.right)
                self._alsa(self._config.source)
            self._split = Split(self._config)
            self._split_conn: QMetaObject.Connection = self._split.finished.connect(
                self.__exit__
            )
            self._exit_split.connect(
                self._split.__exit__, type=Qt.ConnectionType.QueuedConnection
            )
            self._split.moveToThread(self._thread)
            self._thread_conn: QMetaObject.Connection = self._thread.started.connect(
                lambda: self._split(None, None, None),
                type=Qt.ConnectionType.DirectConnection,
            )
            self._thread.start()
            volume_device: QAudioDevice | None = self._config.volume_device
            if volume_device is not None:
                self._volume = VolumeMonitor(self._split.volume, volume_device)
                self._volume_conn: QMetaObject.Connection = (
                    self._volume.finished.connect(self.__exit__)
                )
                self._volume(None, None, None)
        except BaseException as e:
            self.__exit__(type(e), e, e.__traceback__)
            raise
