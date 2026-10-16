import sys
import threading
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
    captureWarnings,
    getLogger,
)
from logging.handlers import RotatingFileHandler
from types import TracebackType
from typing import ClassVar, Literal, TextIO, override

from PySide6.QtCore import (
    QEvent,
    QObject,
    QtMsgType,
    qInstallMessageHandler,
)
from PySide6.QtGui import QWindow
from PySide6.QtWidgets import (
    QMenuBar,
    QScrollBar,
    QSizeGrip,
    QSplitterHandle,
    QStatusBar,
    QToolBar,
    QWidget,
)


class Logger(QObject):
    _types: ClassVar[set[QEvent.Type]] = {
        QEvent.Type.MouseButtonPress,
        QEvent.Type.MouseButtonRelease,
        QEvent.Type.MouseButtonDblClick,
        QEvent.Type.KeyPress,
        QEvent.Type.KeyRelease,
        QEvent.Type.Shortcut,
        QEvent.Type.ShortcutOverride,
        QEvent.Type.Close,
        QEvent.Type.DragEnter,
        QEvent.Type.DragMove,
        QEvent.Type.DragLeave,
        QEvent.Type.Drop,
        QEvent.Type.ContextMenu,
        QEvent.Type.InputMethod,
    }
    _levels: ClassVar[dict[QtMsgType, int]] = {
        QtMsgType.QtDebugMsg: DEBUG,
        QtMsgType.QtInfoMsg: INFO,
        QtMsgType.QtWarningMsg: WARNING,
        QtMsgType.QtCriticalMsg: ERROR,
        QtMsgType.QtFatalMsg: CRITICAL,
    }
    _ignored: ClassVar[set[type[QObject]]] = {
        QMenuBar,
        QScrollBar,
        QSizeGrip,
        QSplitterHandle,
        QStatusBar,
        QToolBar,
        QWidget,
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
                fmt="%(asctime)s | %(levelname)s | %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        rotating_file_handler = RotatingFileHandler(
            filename=filename, maxBytes=1024 * 1024, backupCount=5, encoding="utf-8"
        )
        rotating_file_handler.setFormatter(
            fmt=Formatter(
                fmt="%(asctime)s | %(levelname)-7s [%(name)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        if "--debug" in sys.argv:
            sys.argv.remove("--debug")
            self._debug = True
            basicConfig(level=DEBUG, handlers=(stream_handler, rotating_file_handler))
        else:
            self._debug = False
            basicConfig(level=INFO, handlers=(stream_handler, rotating_file_handler))
        qInstallMessageHandler(
            lambda msg_type, context, message: getLogger(name=context.category).log(
                level=self._levels[msg_type], msg=message
            )
        )
        captureWarnings(capture=True)
        sys.excepthook = self._sys_excepthook
        threading.excepthook = self._threading_excepthook

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> Literal[False]:
        if (
            isinstance(watched, QWindow)
            or type(watched) in self._ignored
            or not event.spontaneous()
        ):
            return False
        type_: QEvent.Type = event.type()
        if type_ not in self._types:
            if self._debug:
                getLogger(name=self._category(watched)).debug(msg=event)
            return False
        else:
            getLogger(name=self._category(watched)).info(msg=event)
        return False

    def _category(self, watched: QObject) -> str:
        parts: list[str] = []
        parent: QObject | None = watched
        while parent is not None:
            parts.append(parent.objectName() or parent.metaObject().className())
            parent = parent.parent()
        return ".".join(reversed(parts))

    @staticmethod
    def _sys_excepthook(
        *exc_info: *tuple[type[BaseException], BaseException, TracebackType | None],
    ) -> None:
        getLogger(name="sys").error(msg="", exc_info=exc_info)

    @staticmethod
    def _threading_excepthook(args: threading.ExceptHookArgs) -> None:
        assert args.exc_value is not None
        getLogger(name="threading").error(
            msg="", exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
        )
