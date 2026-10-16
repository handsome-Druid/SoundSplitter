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

from PySide6.QtCore import (
    QMetaObject,
    QMutex,
    QObject,
    Qt,
    QThread,
    QTimer,
    Signal,
    Slot,
)
from shiboken6 import isValid

from SoundSplitter.external import Config, Split, VolumeMonitor


class Start(QObject):
    finished = Signal(object, object, object)
    _logger: Logger = getLogger(name=__name__)
    _exit_split = Signal(object, object, object)

    class _Thread(QThread):
        runned = Signal(object, object, object)

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
                QTimer.singleShot(0, lambda: self.runned.emit(None, None, None))
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
        self._mutex = QMutex()
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
            self._thread.requestInterruption()
            if hasattr(self, "_thread_conn"):
                self._thread.runned.disconnect(self._thread_conn)
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
            self._split = Split(self._config)
            self._split_conn: QMetaObject.Connection = self._split.finished.connect(
                self.__exit__
            )
            self._exit_split.connect(
                self._split.__exit__, type=Qt.ConnectionType.QueuedConnection
            )
            self._split.moveToThread(self._thread)
            self._thread_conn: QMetaObject.Connection = self._thread.runned.connect(
                lambda: self._split(None, None, None),
                type=Qt.ConnectionType.DirectConnection,
            )
            if self._config.volume_device is not None:
                self._volume = VolumeMonitor(self._config)
                self._volume_conn: QMetaObject.Connection = (
                    self._volume.finished.connect(self.__exit__)
                )
                self._volume(None, None, None)
            self._thread.start()
        except BaseException as e:
            self.__exit__(type(e), e, e.__traceback__)
            raise
