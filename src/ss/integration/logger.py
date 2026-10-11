from copy import copy
from logging import (
    CRITICAL,
    DEBUG,
    ERROR,
    INFO,
    WARNING,
    Formatter,
    LogRecord,
    StreamHandler,
    basicConfig,
    getLogger,
)
from logging import (
    Logger as Logger_,
)
from logging.handlers import RotatingFileHandler
from sys import argv
from typing import ClassVar, Literal, TextIO, override

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QWindow


class Logger(QObject):
    _logger: Logger_ = getLogger(name=__name__)
    _types: ClassVar[set[QEvent.Type]] = {
        QEvent.Type.MouseButtonPress,
        QEvent.Type.MouseButtonRelease,
        QEvent.Type.MouseButtonDblClick,
        QEvent.Type.KeyPress,
        QEvent.Type.KeyRelease,
        QEvent.Type.Shortcut,
        QEvent.Type.ShortcutOverride,
        QEvent.Type.Close,
        QEvent.Type.Show,
        QEvent.Type.Hide,
        QEvent.Type.DragEnter,
        QEvent.Type.DragMove,
        QEvent.Type.DragLeave,
        QEvent.Type.Drop,
        QEvent.Type.ContextMenu,
        QEvent.Type.InputMethod,
    }

    class _Formatter(Formatter):
        @override
        def format(self, record: LogRecord) -> str:
            colors: dict[int, str] = {
                DEBUG: "\033[36m",
                INFO: "\033[32m",
                WARNING: "\033[33m",
                ERROR: "\033[31m",
                CRITICAL: "\033[35m",
            }
            record = copy(x=record)
            record.levelname = (
                f"{colors.get(record.levelno, '')}{record.levelname:^7}\033[0m"
            )
            return super().format(record)

    @override
    def __init__(
        self,
        /,
        filename: str,
        parent: QObject | None = None,
        *,
        objectName: str | None = None,
    ) -> None:
        super().__init__(parent, objectName=objectName)
        stream_handler: StreamHandler[TextIO] = StreamHandler()
        stream_handler.setFormatter(
            fmt=self._Formatter(
                fmt="%(asctime)s | %(levelname)s | %(message)s", datefmt="%H:%M:%S"
            )
        )
        rotating_file_handler = RotatingFileHandler(
            filename=filename, maxBytes=1024 * 1024, backupCount=5, encoding="utf-8"
        )
        rotating_file_handler.setFormatter(
            fmt=Formatter(
                fmt="%(asctime)s | %(levelname)-7s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        if "--debug" in argv:
            argv.remove("--debug")
            self._debug = True
            basicConfig(level=DEBUG, handlers=(stream_handler, rotating_file_handler))
        else:
            self._debug = False
            basicConfig(level=INFO, handlers=(stream_handler, rotating_file_handler))

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> Literal[False]:
        if isinstance(watched, QWindow) or not event.spontaneous():
            return False
        type: QEvent.Type = event.type()
        if type not in self._types:
            if self._debug:
                self._logger.debug(
                    msg=f"[{watched.objectName()}] [{watched.metaObject().className()}] [{type.name}] -> {event}"
                )
            return False
        else:
            self._logger.info(
                msg=f"[{watched.objectName()}] [{watched.metaObject().className()}] [{type.name}] {event}"
            )
        return False
