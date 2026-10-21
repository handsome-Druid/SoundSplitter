from collections.abc import Callable, Collection
from ctypes import WinError, windll
from ctypes.wintypes import BOOL, DWORD, LPCWSTR
from os import link
from subprocess import list2cmdline
from sys import argv, exit, modules
from typing import NoReturn, override

from PySide6.QtCore import (
    Q_ARG,
    QDir,
    QEvent,
    QFile,
    QFileInfo,
    QLibraryInfo,
    QLocale,
    QLockFile,
    QMessageLogContext,
    QMetaObject,
    QObject,
    QProcess,
    QProcessEnvironment,
    QSettings,
    QStorageInfo,
    Qt,
    QTemporaryDir,
    QThread,
    QTimer,
    QtMsgType,
    QTranslator,
    Signal,
    Slot,
    qCritical,
    qInfo,
    qInstallMessageHandler,
    qWarning,
)
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox, QTextBrowser, QWizard

from .resources import resources_rc

modules["resources_rc"] = resources_rc
from .ui import Ui_Wizard


class Uninstall(QObject):
    start_uninstall = Signal(bool)
    APPLICATION_NAME: str = "SoundSplitter"
    _start_menu = _desktop = _startup = False
    _program_data = QDir(
        path=QProcessEnvironment.systemEnvironment().value("ProgramData")
    )
    _data_dir = QDir(path=_program_data.absoluteFilePath(APPLICATION_NAME))
    _program_files = QDir(
        path=QProcessEnvironment.systemEnvironment().value("ProgramFiles")
    )
    _app_dir = QDir(path=_program_files.absoluteFilePath(APPLICATION_NAME))
    _executable: str = _app_dir.filePath(APPLICATION_NAME + ".exe")

    @override
    def __init__(
        self, /, parent: QObject | None = None, *, objectName: str | None = None
    ) -> None:
        super().__init__(parent, objectName=objectName)
        self._app = QApplication()
        self._ui = Ui_Wizard()
        self._wizard = QWizard()
        self._busy = True
        reject: Callable[[], None] = self._wizard.reject
        self._wizard.reject = lambda: None if self._busy else reject()
        self._wizard.closeEvent = lambda event: (
            event.ignore() if self._busy else event.accept()
        )
        self._wizard.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, on=False)
        self._ui.setupUi(Wizard=self._wizard)
        self._app.setApplicationName(self._wizard.windowTitle())
        qInstallMessageHandler(self._message_handler)
        try:
            if not windll.shell32.IsUserAnAdmin():
                if (
                    windll.shell32.ShellExecuteW(
                        None, "runas", argv[0], list2cmdline(seq=argv[1:]), None, 1
                    )
                    <= 32
                ):
                    raise RuntimeError("Please run as administrator.")
                exit(0)
            if not QDir().mkpath(self._data_dir.absolutePath()):
                raise OSError(
                    self.tr(
                        "Unable to create the required folder in the local data directory. "
                        "Please check permissions or available disk space."
                    )
                )
            changeEvent_: Callable[[QEvent], None] = self._wizard.changeEvent
            self._thread = QThread(parent=self._wizard)
            self._app.aboutToQuit.connect(self._thread.quit)
            self._app.aboutToQuit.connect(self._thread.wait)
            if "--step2" in argv:
                self._app.aboutToQuit.connect(self._on_about_to_quit)

                def changeEvent(event: QEvent) -> None:
                    match event.type():
                        case QEvent.Type.LanguageChange:
                            self._ui.retranslateUi(Wizard=self._wizard)
                            self._ui.copyPage.setButtonText(
                                self._wizard.WizardButton.BackButton, self.tr("< &Back")
                            )
                            self._ui.copyPage.setButtonText(
                                self._wizard.WizardButton.NextButton, self.tr("&Next >")
                            )
                            self._ui.copyPage.setButtonText(
                                self._wizard.WizardButton.CancelButton,
                                self.tr("Cancel"),
                            )
                            self._ui.optionPage.setButtonText(
                                self._wizard.WizardButton.NextButton,
                                self.tr("&Uninstall"),
                            )
                            changeEvent_(event)
                        case _:
                            changeEvent_(event)

                self._wizard.changeEvent = changeEvent
                translation_dir = QDir(
                    path=globals()["__compiled__"].python_runtime_dir
                    + "/translations/uninstall"
                )
                qt_path: str = QLibraryInfo.path(
                    QLibraryInfo.LibraryPath.TranslationsPath
                )

                def showPopup(
                    showPopup: Callable[[], None] = self._ui.languageComboBox.showPopup,
                ) -> None:
                    current: str = self._ui.languageComboBox.currentText()
                    self._ui.languageComboBox.clear()
                    self._ui.languageComboBox.addItem("en_US")
                    for file in translation_dir.entryList(
                        ("*.qm",), filters=QDir.Filter.Files
                    ):
                        translator = QTranslator()
                        if not translator.load(translation_dir.filePath(file)):
                            continue
                        locale: QLocale | None = None
                        locale_ = QLocale(translator.language())
                        if locale_.language() != QLocale.Language.C:
                            locale = locale_
                        else:
                            locale_ = QLocale(
                                file.removesuffix(".qm").replace("-", "_")
                            )
                            if locale_.language() != QLocale.Language.C:
                                locale = locale_
                        qt_translator = None
                        if locale is not None:
                            qt_translator = QTranslator()
                            if not qt_translator.load(
                                locale, "qtbase", "_", directory=qt_path
                            ):
                                qt_translator = None
                        self._ui.languageComboBox.addItem(
                            locale.name() if locale is not None else file,
                            userData=(qt_translator, translator),
                        )
                    index: int = self._ui.languageComboBox.findText(current)
                    if index >= 0:
                        self._ui.languageComboBox.setCurrentIndex(index)
                    showPopup()

                self._ui.languageComboBox.showPopup = showPopup
                self._ui.languageComboBox.addItem("en_US")
                self._ui.languageComboBox.setCurrentIndex(
                    self._ui.languageComboBox.count() - 1
                )
                self._ui.languageComboBox.activated.connect(
                    self._on_language_combo_box_activated
                )
                self._ui.uninstalltextBrowser.hide()
                self._ui.uninstallToolButton.toggled.connect(
                    lambda checked: (
                        self._ui.uninstalltextBrowser.show()
                        if checked
                        else self._ui.uninstalltextBrowser.hide()
                    )
                )
                self._ui.uninstallProgressBar.setRange(0, 100)
                self._ui.uninstallProgressBar.setValue(0)
                self._wizard.setCurrentId(1)
                self._wizard.setButtonLayout(
                    [
                        self._wizard.WizardButton.Stretch,
                        self._wizard.WizardButton.CancelButton,
                    ]
                )
                self._wizard.button(self._wizard.WizardButton.CancelButton).setEnabled(
                    False
                )
                self._uninstall = self._Uninstall()
                self._uninstall.moveToThread(self._thread)
                self._thread.started.connect(
                    self._uninstall._on_started, type=Qt.ConnectionType.QueuedConnection
                )
                self.start_uninstall.connect(
                    self._uninstall.__call__, type=Qt.ConnectionType.QueuedConnection
                )
                self._uninstall.ready.connect(self._on_uninstall_ready)
                self._uninstall.progress_bar.connect(
                    self._ui.uninstallProgressBar.setValue
                )
                self._uninstall.finished.connect(self._on_uninstall_finished)
                self._thread.finished.connect(self._uninstall.deleteLater)
                self._wizard.currentIdChanged.connect(self._on_current_id_changed)
            else:
                self._lock = QLockFile(
                    self._data_dir.absoluteFilePath("uninstall.lock")
                )
                self._lock.setStaleLockTime(0)
                if not self._lock.tryLock(0):
                    if self._lock.error() == QLockFile.LockError.LockFailedError:
                        raise RuntimeError(
                            self.tr(
                                "The uninstaller is already running. Please do not launch it again."
                            )
                        )
                    else:
                        raise RuntimeError(
                            self.tr(
                                "Could not create the single-instance lock. Check the directory permissions."
                            )
                        )
                self._temp = QTemporaryDir()
                if not self._temp.isValid():
                    raise OSError(self._temp.errorString())
                self._app.aboutToQuit.connect(
                    lambda: self._temp.remove() if self._temp.autoRemove() else None
                )
                self._wizard.setButtonLayout(
                    [
                        self._wizard.WizardButton.Stretch,
                        self._wizard.WizardButton.CancelButton,
                    ]
                )
                self._wizard.button(self._wizard.WizardButton.CancelButton).setEnabled(
                    False
                )
                self._ui.copyTextBrowser.hide()
                self._ui.copyToolButton.toggled.connect(
                    lambda checked: (
                        self._ui.copyTextBrowser.show()
                        if checked
                        else self._ui.copyTextBrowser.hide()
                    )
                )
                self._ui.copyProgressBar.setRange(0, 0)
                self._copy = self._Copy(self._temp)
                self._copy.moveToThread(self._thread)
                self._thread.started.connect(self._copy.__call__)
                self._thread.finished.connect(self._copy.deleteLater)
                self._copy.finished.connect(
                    self._on_copy_finished, type=Qt.ConnectionType.QueuedConnection
                )

        except SystemExit:
            raise
        except BaseException as e:
            self._on_critical(str(object=e))
            raise

    def __call__(self) -> NoReturn:
        self._wizard.show()
        self._thread.start()
        exit(self._app.exec())

    class _Uninstall(QObject):
        ready = Signal()
        progress_bar = Signal(int)
        finished = Signal(object)

        @Slot()
        def _on_started(self) -> None:
            try:
                socket = QLocalSocket()
                socket.connectToServer(Uninstall.APPLICATION_NAME + ".Uninstall")
                if not socket.waitForConnected(msecs=10000):
                    raise RuntimeError(
                        self.tr("Failed to connect to the original uninstaller: ")
                        + socket.errorString()
                    )
                if socket.write(b"EXIT") != 4:
                    raise RuntimeError(socket.errorString())
                if not socket.waitForBytesWritten(msecs=10000):
                    raise RuntimeError(socket.errorString())
                socket.disconnectFromServer()
                self._lock = QLockFile(
                    Uninstall._data_dir.absoluteFilePath("uninstall.lock")
                )
                self._lock.setStaleLockTime(0)
                self.thread().finished.connect(
                    self._lock.unlock, type=Qt.ConnectionType.DirectConnection
                )
                if not self._lock.tryLock(10000):
                    raise RuntimeError(
                        self.tr(
                            "Failed to acquire the uninstaller lock after the original process exited."
                        )
                    )
                self.ready.emit()
            except BaseException as e:
                self.thread().quit()
                qCritical(self.tr("Uninstallation failed: ") + str(object=e))
                raise

        @Slot(bool)
        def __call__(self, keep_data: bool) -> None:
            try:
                self.progress_bar.emit(0)
                self._app_lock = QLockFile(
                    Uninstall._data_dir.absoluteFilePath(".lock")
                )
                self._app_lock.setStaleLockTime(0)
                self.thread().finished.connect(
                    self._app_lock.unlock, type=Qt.ConnectionType.DirectConnection
                )
                if not self._app_lock.tryLock(0):
                    qInfo(
                        self.tr("Closing the running instance: ")
                        + Uninstall.APPLICATION_NAME
                    )
                    socket = QLocalSocket()
                    socket.connectToServer(Uninstall.APPLICATION_NAME)
                    if not socket.waitForConnected(msecs=10000):
                        raise RuntimeError(
                            self.tr(
                                "Failed to close the running instance. Please close it manually and try again."
                            )
                        )
                    if socket.write(b"EXIT") != 4:
                        raise RuntimeError(socket.errorString())
                    if not socket.waitForBytesWritten(msecs=10000):
                        raise RuntimeError(socket.errorString())
                    socket.disconnectFromServer()
                    if not self._app_lock.tryLock(10000):
                        raise RuntimeError(
                            self.tr(
                                "Failed to close the running instance. Please close it manually and try again."
                            )
                        )
                self.progress_bar.emit(10)
                app_dir: QDir = Uninstall._app_dir
                qInfo(
                    self.tr("Deleting the installation directory: ")
                    + app_dir.absolutePath()
                )
                if app_dir.exists() and not app_dir.removeRecursively():
                    raise OSError(
                        self.tr("Failed to remove the installation directory: ")
                        + app_dir.absolutePath()
                    )
                self.progress_bar.emit(40)
                desktop_dir = QDir(
                    path=QProcessEnvironment.systemEnvironment().value("Public")
                    + r"\Desktop"
                )
                shortcut_dir = QDir(
                    path=Uninstall._program_data.absolutePath()
                    + r"\Microsoft\Windows\Start Menu\Programs"
                )
                for directory in (desktop_dir, shortcut_dir):
                    shortcut = directory.filePath(Uninstall.APPLICATION_NAME + ".lnk")
                    if QFile.exists(shortcut) or QFileInfo(shortcut).isShortcut():
                        qInfo(self.tr("Deleting shortcut: ") + shortcut)
                        if not QFile.remove(shortcut):
                            raise OSError(
                                self.tr("Failed to delete shortcut: ") + shortcut
                            )
                self.progress_bar.emit(60)
                uninstall_reg = QSettings(
                    r"HKEY_LOCAL_MACHINE\Software\Microsoft\Windows\CurrentVersion\Uninstall",
                    QSettings.Format.NativeFormat,
                )
                startup_reg = QSettings(
                    r"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run",
                    QSettings.Format.NativeFormat,
                )
                for settings in (uninstall_reg, startup_reg):
                    qInfo(
                        self.tr("Deleting registry entry: ")
                        + Uninstall.APPLICATION_NAME
                    )
                    settings.remove(Uninstall.APPLICATION_NAME)
                    settings.sync()
                    if settings.status() != QSettings.Status.NoError:
                        raise OSError(self.tr("Failed to remove registry entries."))
                self.progress_bar.emit(80)
                if not keep_data:
                    self._app_lock.unlock()
                    self._lock.unlock()
                    data_dir: QDir = Uninstall._data_dir
                    qInfo(self.tr("Deleting user data: ") + data_dir.absolutePath())
                    if data_dir.exists() and not data_dir.removeRecursively():
                        raise OSError(
                            self.tr("Failed to remove the user data directory: ")
                            + data_dir.absolutePath()
                        )
                self.progress_bar.emit(100)
                self.finished.emit(None)
            except BaseException as e:
                self.finished.emit(e)
                raise
            finally:
                self.thread().quit()

    class _Copy(QObject):
        finished = Signal(object)

        @override
        def __init__(self, temp: QTemporaryDir, /) -> None:
            super().__init__()
            self._temp: QTemporaryDir = temp

        def __call__(self) -> None:
            try:
                if not self._temp.isValid():
                    raise OSError(self._temp.errorString())
                containing_dir: str = QFileInfo(argv[0]).absolutePath()
                if not QFileInfo(
                    QDir(containing_dir).filePath("uninstall.exe")
                ).isFile():
                    raise OSError(
                        self.tr("Uninstaller payload is missing: ") + containing_dir
                    )
                containing_storage = QStorageInfo(containing_dir)
                temp_storage = QStorageInfo(self._temp.path())
                if (
                    containing_storage.isValid()
                    and temp_storage.isValid()
                    and containing_storage.device() == temp_storage.device()
                ):
                    self._link_dir(containing_dir, self._temp.path())
                else:
                    self._copy_dir(containing_dir, self._temp.path())
                self.finished.emit(None)
            except BaseException as e:
                self.finished.emit(e)
                raise
            finally:
                self.thread().quit()

        def _copy_dir(self, src: str, dst: str, /) -> None:
            if not QDir(src).exists() or not QDir(src).isReadable():
                raise OSError(self.tr("Unable to read directory: ") + src)
            for info in QDir(path=src).entryInfoList(
                filters=QDir.Filter.AllEntries
                | QDir.Filter.NoDotAndDotDot
                | QDir.Filter.Hidden
                | QDir.Filter.System
            ):
                if info.isSymLink() or info.isJunction():
                    raise OSError(
                        self.tr("Links are not supported in the payload: ")
                        + info.absoluteFilePath()
                    )
                target: str = QDir(path=dst).filePath(info.fileName())
                if info.isDir():
                    if not QDir().mkpath(target):
                        raise OSError("Create directory failed: " + target)
                    self._copy_dir(info.absoluteFilePath(), target)
                else:
                    qInfo(self.tr("Copying file: ") + info.absoluteFilePath())
                    if not QFile.copy(info.absoluteFilePath(), target):
                        raise OSError(self.tr("Copy failed: ") + target)

        def _link_dir(self, src: str, dst: str, /) -> None:
            if not QDir(src).exists() or not QDir(src).isReadable():
                raise OSError(self.tr("Unable to read directory: ") + src)
            dir_ = QDir()
            for info in QDir(path=src).entryInfoList(
                filters=QDir.Filter.AllEntries
                | QDir.Filter.NoDotAndDotDot
                | QDir.Filter.Hidden
                | QDir.Filter.System
            ):
                if info.isSymLink() or info.isJunction():
                    raise OSError(
                        self.tr("Links are not supported in the payload: ")
                        + info.absoluteFilePath()
                    )
                target: str = QDir(path=dst).filePath(info.fileName())
                if info.isDir():
                    if not dir_.mkpath(target):
                        raise OSError("Create directory failed: " + target)
                    self._link_dir(info.absoluteFilePath(), target)
                else:
                    qInfo(self.tr("Linking file: ") + info.absoluteFilePath())
                    try:
                        link(src=info.absoluteFilePath(), dst=target)
                    except OSError:
                        if not QFile.copy(info.absoluteFilePath(), target):
                            raise OSError(self.tr("Copy failed: ") + target)

    class _Setp2(QObject):
        timeout = Signal()
        finished = Signal()

        @override
        def __init__(self, temp: QTemporaryDir, /) -> None:
            super().__init__()
            self._temp: QTemporaryDir = temp
            self._done = False

        def __call__(self) -> None:
            try:
                self._server = QLocalServer(self)
                self._timer = QTimer(parent=self)
                self._timer.setSingleShot(True)
                self._timer.setInterval(10000)
                self._timer.timeout.connect(self._on_timeout)
                if not self._server.listen(Uninstall.APPLICATION_NAME + ".Uninstall"):
                    raise RuntimeError(self._server.errorString())
                self._server.newConnection.connect(self._on_new_connection)
                process = QProcess()
                if not process.startDetached(
                    self._temp.filePath("uninstall.exe"),
                    arguments=("--step2",),
                    workingDirectory=self._temp.path(),
                )[0]:
                    raise RuntimeError(
                        self.tr("Unable to start the temporary uninstaller: ")
                        + self._temp.path()
                    )
                self._temp.setAutoRemove(False)
                self._timer.start()
            except BaseException as e:
                self._done = True
                if hasattr(self, "_timer"):
                    self._timer.stop()
                if hasattr(self, "_server"):
                    self._server.close()
                    for socket in self._server.findChildren(QLocalSocket):
                        socket.abort()
                        socket.deleteLater()
                self.thread().quit()
                qCritical(self.tr("Uninstallation failed: ") + str(object=e))
                raise

        @Slot()
        def _on_new_connection(self) -> None:
            if self._done or not self._server.hasPendingConnections():
                return
            socket: QLocalSocket = self._server.nextPendingConnection()
            socket.disconnected.connect(socket.deleteLater)

            @Slot()
            def on_ready_read() -> None:
                if self._done:
                    return
                if socket.bytesAvailable() >= 4:
                    if socket.read(4).data() == b"EXIT":
                        self._done = True
                        self._timer.stop()
                        self._server.close()
                        for connection in self._server.findChildren(QLocalSocket):
                            connection.abort()
                            connection.deleteLater()
                        self.thread().quit()
                        self.finished.emit()
                    else:
                        socket.disconnectFromServer()

            socket.readyRead.connect(on_ready_read)
            on_ready_read()

        @Slot()
        def _on_timeout(self) -> None:
            if self._done:
                return
            self._done = True
            self._timer.stop()
            self._server.close()
            for socket in self._server.findChildren(QLocalSocket):
                socket.abort()
                socket.deleteLater()
            self.thread().quit()
            self.timeout.emit()

    def _message_handler(
        self, msg_type: QtMsgType, context: QMessageLogContext, msg: str
    ) -> None:
        if "--step2" in argv:
            text_browser: QTextBrowser = self._ui.uninstalltextBrowser
        else:
            text_browser = self._ui.copyTextBrowser
        if msg_type == QtMsgType.QtWarningMsg:
            if "QFont::setPointSize" in msg:
                return
            QMetaObject.invokeMethod(
                text_browser,
                "append",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, self.tr("Warning: ") + msg),
            )
        elif msg_type == QtMsgType.QtCriticalMsg:
            QMetaObject.invokeMethod(
                self,
                "_on_critical",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, msg),
            )
        else:
            QMetaObject.invokeMethod(
                text_browser,
                "append",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, msg),
            )

    @Slot(str)
    def _on_critical(self, msg: str, /) -> None:
        if hasattr(self, "_thread"):
            self._thread.quit()
            self._thread.wait()
        self._busy = False
        if hasattr(self, "_temp") and not self._temp.remove():
            qWarning(
                self.tr("Unable to remove the temporary directory: ")
                + self._temp.path()
            )
        if "--step2" in argv and self._wizard.currentId() == 3:
            self._ui.progressPage.setSubTitle(self.tr("Uninstallation Failed!"))
            self._ui.label_4.setText(self.tr("Uninstallation failed!") + "\n" + msg)
        else:
            self._ui.waitPage.setSubTitle(self.tr("Uninstallation Failed!"))
            self._ui.waitLabel.setText(self.tr("Uninstallation failed!") + "\n" + msg)
            self._wizard.setCurrentId(1)
        self._wizard.setButtonLayout(
            [self._wizard.WizardButton.Stretch, self._wizard.WizardButton.CancelButton]
        )
        self._wizard.button(self._wizard.WizardButton.CancelButton).setEnabled(True)
        self._wizard.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, on=True)
        self._wizard.show()
        QMessageBox.critical(
            self._wizard if hasattr(self, "_wizard") else None,
            self._app.applicationName(),
            self.tr("Critical: ") + msg,
        )

    @Slot()
    def _on_about_to_quit(self) -> None:
        try:
            move_file_ex = windll.kernel32.MoveFileExW
            move_file_ex.argtypes = (LPCWSTR, LPCWSTR, DWORD)
            move_file_ex.restype = BOOL
            movefile_delay_until_reboot = 0x4
            pending: list[tuple[str, bool]] = [
                (QFileInfo(argv[0]).absolutePath(), False)
            ]
            while pending:
                path, visited = pending.pop()
                info = QFileInfo(path)
                if (
                    not visited
                    and info.isDir()
                    and not info.isSymLink()
                    and not info.isJunction()
                ):
                    pending.append((path, True))
                    for child in QDir(path).entryInfoList(
                        filters=QDir.Filter.AllEntries
                        | QDir.Filter.NoDotAndDotDot
                        | QDir.Filter.Hidden
                        | QDir.Filter.System
                    ):
                        pending.append((child.absoluteFilePath(), False))
                    continue
                if not move_file_ex(
                    QDir.toNativeSeparators(path), None, movefile_delay_until_reboot
                ):
                    error: OSError = WinError()
                    error.filename = QDir.toNativeSeparators(path)
                    raise error
        except BaseException as e:
            qCritical(
                self.tr("Failed to schedule temporary directory cleanup on restart: ")
                + str(object=e)
            )
            raise

    @Slot()
    def _on_uninstall_ready(self) -> None:
        self._busy = False
        self._wizard.setCurrentId(2)
        self._wizard.setButtonLayout(
            [
                self._wizard.WizardButton.Stretch,
                self._wizard.WizardButton.NextButton,
                self._wizard.WizardButton.CancelButton,
            ]
        )
        self._ui.optionPage.setButtonText(
            self._wizard.WizardButton.NextButton, self.tr("&Uninstall")
        )
        self._wizard.button(self._wizard.WizardButton.CancelButton).setEnabled(True)
        self._wizard.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, on=True)
        self._wizard.show()

    @Slot(int)
    def _on_current_id_changed(self, page_id: int, /) -> None:
        if page_id == 3 and not self._busy:
            self._busy = True
            self._wizard.setButtonLayout(
                [
                    self._wizard.WizardButton.Stretch,
                    self._wizard.WizardButton.CancelButton,
                ]
            )
            self._wizard.button(self._wizard.WizardButton.CancelButton).setEnabled(
                False
            )
            self.start_uninstall.emit(self._ui.dataCheckBox.isChecked())

    @Slot(object)
    def _on_uninstall_finished(self, e: None | BaseException) -> None:
        self._thread.wait()
        self._busy = False
        if e is not None:
            self._on_critical(self.tr("Uninstallation failed: ") + str(object=e))
        else:
            self._ui.progressPage.setSubTitle(
                self.tr("SoundSplitter has been removed from your computer.")
            )
            self._ui.label_4.setText(self.tr("Uninstallation complete."))
            self._wizard.setButtonLayout(
                [
                    self._wizard.WizardButton.Stretch,
                    self._wizard.WizardButton.FinishButton,
                ]
            )
            self._wizard.button(self._wizard.WizardButton.FinishButton).setEnabled(True)
            self._wizard.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, on=True)
            self._wizard.show()

    @Slot()
    def _on_language_combo_box_activated(self) -> None:
        translators: Collection[QTranslator | None] | None = getattr(
            self, "_translators", None
        )
        if translators is not None:
            for translator in translators:
                if translator is not None:
                    self._app.removeTranslator(translator)
        self._translators: Collection[QTranslator | None] | None = (
            self._ui.languageComboBox.currentData(Qt.ItemDataRole.UserRole)
        )
        if self._translators is not None:
            for translator in self._translators:
                if translator is not None:
                    self._app.installTranslator(translator)

    @Slot(object)
    def _on_copy_finished(self, e: None | BaseException) -> None:
        self._thread.wait()
        if e is None:
            self._wizard.setCurrentId(1)
            self._step2 = self._Setp2(self._temp)
            self._step2.moveToThread(self._thread)
            self._step2.timeout.connect(self._on_timeout)
            self._step2.finished.connect(self._on_handoff_finished)
            self._thread.started.connect(self._step2.__call__)
            self._thread.finished.connect(self._step2.deleteLater)
            self._thread.start()
        else:
            self._on_critical(self.tr("Uninstallation failed: ") + str(object=e))

    @Slot()
    def _on_handoff_finished(self) -> None:
        self._thread.wait()
        self._busy = False
        self._app.quit()

    @Slot()
    def _on_timeout(self) -> None:
        self._on_critical(
            self.tr(
                "The temporary uninstaller did not complete the handoff within 10 seconds: "
            )
            + self._temp.path()
        )


def main() -> NoReturn:
    Uninstall()()
