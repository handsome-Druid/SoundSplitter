from collections.abc import Callable, Collection
from ctypes import windll
from itertools import chain
from os import link
from subprocess import list2cmdline
from sys import argv, exit, modules
from typing import ClassVar, NoReturn

from PySide6.QtCore import (
    Q_ARG,
    QDate,
    QDir,
    QDirIterator,
    QEvent,
    QFile,
    QLibraryInfo,
    QLocale,
    QLockFile,
    QMessageLogContext,
    QMetaObject,
    QObject,
    QProcess,
    QProcessEnvironment,
    QSettings,
    QStandardPaths,
    QStorageInfo,
    Qt,
    QThread,
    QtMsgType,
    QTranslator,
    Signal,
    Slot,
    qCritical,
    qInfo,
    qInstallMessageHandler,
    qWarning,
)
from PySide6.QtGui import QDesktopServices, QTextCursor
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtNetwork import QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox, QWizard

from setup.__about__ import __author__, __version__
from setup.resources import resources_rc

modules["resources_rc"] = resources_rc

from setup.ui import Ui_Wizard


class Setup(QObject):
    APPLICATION_NAME: str = "SoundSplitter"
    OLD_APPLICATION_NAMES: ClassVar[tuple[str]] = ("SoundSpliter",)
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

    class _Install(QObject):
        progress_bar = Signal(int)

        @Slot()
        def __call__(self) -> None:
            try:
                program_files: QDir = Setup._program_files
                app_dir: QDir = Setup._app_dir
                executable: str = Setup._executable
                program_data: QDir = Setup._program_data
                shortcut_dir = QDir(
                    path=program_data.absolutePath()
                    + r"\Microsoft\Windows\Start Menu\Programs"
                )
                desktop_dir = QDir(
                    path=QProcessEnvironment.systemEnvironment().value("Public")
                    + r"\Desktop"
                )
                data_dir: QDir = Setup._data_dir
                app_data = QDir(
                    path=QStandardPaths.writableLocation(
                        QStandardPaths.StandardLocation.GenericConfigLocation
                    )
                )
                uninstall_reg = QSettings(
                    QSettings.Scope.SystemScope,
                    r"Microsoft\Windows\CurrentVersion\Uninstall",
                )
                startup_reg = QSettings(
                    QSettings.Scope.UserScope,
                    r"Microsoft\Windows\CurrentVersion\Run",
                )
                self.progress_bar.emit(10)
                for name in chain(
                    Setup.OLD_APPLICATION_NAMES, (Setup.APPLICATION_NAME,)
                ):
                    for old_data in (
                        QDir(path=program_data.absoluteFilePath(name)),
                        QDir(path=app_data.absoluteFilePath(name)),
                    ):
                        if old_data.exists():
                            locker = QLockFile(old_data.absoluteFilePath(".lock"))
                            locker.setStaleLockTime(0)
                            if not locker.tryLock(0):
                                qInfo(self.tr("Closing the running instance: ") + name)
                                socket = QLocalSocket()
                                socket.connectToServer(name)
                                if not socket.waitForConnected(msecs=10000):
                                    raise RuntimeError(
                                        self.tr(
                                            "Failed to close the running instance. Please close it manually and try again."
                                        )
                                    )
                                socket.write(b"EXIT")
                                if not socket.waitForBytesWritten(
                                    msecs=10000
                                ) or not locker.tryLock(10000):
                                    raise RuntimeError(
                                        self.tr(
                                            "Failed to close the running instance. Please close it manually and try again."
                                        )
                                    )
                            locker.unlock()
                            if old_data != data_dir:
                                qInfo(
                                    self.tr(
                                        "Migrating data from old installation directory: "
                                    )
                                    + old_data.absolutePath()
                                )
                                try:
                                    self._rename_dir(
                                        old_data.absolutePath(), data_dir.absolutePath()
                                    )
                                    if not old_data.removeRecursively():
                                        qWarning(
                                            self.tr(
                                                "Failed to remove the old data directory: "
                                            )
                                            + old_data.absolutePath()
                                        )
                                except OSError:
                                    qWarning(
                                        self.tr(
                                            "Failed to migrate data from old installation directory: "
                                        )
                                        + old_data.absolutePath()
                                    )
                    if QFile.exists(desktop_dir.filePath(name + ".lnk")):
                        qInfo(self.tr("Deleting old Desktop shortcut: ") + name)
                        if not QFile.remove(desktop_dir.filePath(name + ".lnk")):
                            qWarning(
                                self.tr("Failed to delete the old Desktop shortcut: ")
                                + name
                            )
                    if QFile.exists(shortcut_dir.filePath(name + ".lnk")):
                        qInfo(self.tr("Deleting old Start Menu shortcut: ") + name)
                        if not QFile.remove(shortcut_dir.filePath(name + ".lnk")):
                            qWarning(
                                self.tr(
                                    "Failed to delete the old Start Menu shortcut: "
                                )
                                + name
                            )
                    old_app_dir = QDir(path=program_files.absoluteFilePath(name))
                    if old_app_dir.exists():
                        qInfo(
                            self.tr("Deleting existing installation directory: ")
                            + old_app_dir.absolutePath()
                        )
                        if not old_app_dir.removeRecursively():
                            if old_app_dir == app_dir:
                                raise RuntimeError(
                                    self.tr(
                                        "Failed to remove the existing installation directory: "
                                        + app_dir.absolutePath()
                                    )
                                )
                            else:
                                qWarning(
                                    self.tr(
                                        "Failed to remove the old installation directory: "
                                        + old_app_dir.absolutePath()
                                    )
                                )
                    if name in startup_reg.childKeys():
                        qInfo(self.tr("Deleting startup registry entry: ") + name)
                        startup_reg.remove(name)
                    if name in uninstall_reg.childGroups():
                        qInfo(self.tr("Deleting registry key: ") + name)
                        uninstall_reg.remove(name)
                self.progress_bar.emit(30)
                process = QProcess()
                process.setProcessChannelMode(process.ProcessChannelMode.MergedChannels)
                process.readyReadStandardOutput.connect(
                    lambda: qInfo(
                        bytes(process.readAllStandardOutput().data())
                        .decode(f"cp{windll.kernel32.GetOEMCP()}", errors="replace")
                        .rstrip()
                    )
                )
                process.start(
                    "icacls",
                    arguments=(
                        data_dir.absolutePath(),
                        "/grant",
                        "*S-1-5-32-545:(OI)(CI)M",
                        "/C",
                        "/Q",
                    ),
                )
                if not process.waitForFinished() or process.exitCode():
                    raise OSError(
                        self.tr("Failed to set permissions for the data directory.")
                    )
                uninstall_reg.sync()
                self.progress_bar.emit(40)
                qInfo(self.tr("Copying files to the installation directory..."))
                if not app_dir.mkpath("."):
                    raise OSError(
                        self.tr("Failed to create the installation directory.")
                    )
                source: str = globals()["__compiled__"].python_runtime_dir
                source_storage = QStorageInfo(source)
                app_storage = QStorageInfo(app_dir.absolutePath())
                if (
                    source_storage.isValid()
                    and app_storage.isValid()
                    and source_storage.device() == app_storage.device()
                ):
                    self._link_dir(
                        globals()["__compiled__"].python_runtime_dir,
                        app_dir.absolutePath(),
                    )
                    process = QProcess()
                    process.setProcessChannelMode(
                        process.ProcessChannelMode.MergedChannels
                    )
                    process.readyReadStandardOutput.connect(
                        lambda: qInfo(
                            bytes(process.readAllStandardOutput().data())
                            .decode(f"cp{windll.kernel32.GetOEMCP()}", errors="replace")
                            .rstrip()
                        )
                    )
                    process.start(
                        "icacls",
                        arguments=(
                            app_dir.absolutePath(),
                            "/reset",
                            "/T",
                            "/C",
                            "/Q",
                        ),
                    )
                    if not process.waitForFinished() or process.exitCode():
                        raise OSError(
                            self.tr(
                                "Failed to set permissions for the installation directory."
                            )
                        )
                else:
                    self._copy_dir(source, app_dir.absolutePath())
                qInfo(self.tr("Creating registry entries for uninstallation..."))
                settings = QSettings(
                    QSettings.Scope.SystemScope,
                    r"Microsoft\Windows\CurrentVersion\Uninstall",
                    application=Setup.APPLICATION_NAME,
                )
                settings.setValue("DisplayName", Setup.APPLICATION_NAME)
                settings.setValue("DisplayVersion", __version__)
                settings.setValue("Publisher", __author__)
                settings.setValue("InstallLocation", app_dir.absolutePath())
                settings.setValue(
                    "InstallDate", QDate.currentDate().toString("yyyyMMdd")
                )
                settings.setValue("DisplayIcon", executable)
                settings.setValue("EstimatedSize", self._directory_size(app_dir))
                settings.setValue("VersionMajor", int(__version__.split(sep=".")[0]))
                settings.setValue("VersionMinor", int(__version__.split(sep=".")[1]))
                settings.setValue(
                    "UninstallString",
                    '"' + app_dir.filePath("uninstall.exe") + '"',
                )
                settings.setValue("NoModify", 1)
                settings.setValue("NoRepair", 1)
                settings.sync()
                self.progress_bar.emit(80)
                if Setup._start_menu:
                    qInfo(self.tr("Creating Start Menu shortcut..."))
                    if not QFile.link(
                        executable,
                        shortcut_dir.filePath(Setup.APPLICATION_NAME + ".lnk"),
                    ):
                        qWarning(self.tr("Failed to create the Start Menu shortcut."))
                self.progress_bar.emit(90)
                if Setup._desktop:
                    qInfo(self.tr("Creating Desktop shortcut..."))
                    if not QFile.link(
                        executable,
                        desktop_dir.filePath(Setup.APPLICATION_NAME + ".lnk"),
                    ):
                        qWarning(self.tr("Failed to create the Desktop shortcut."))
                if Setup._startup:
                    startup_reg.setValue(Setup.APPLICATION_NAME, '"' + executable + '"')
                else:
                    startup_reg.remove(Setup.APPLICATION_NAME)
                startup_reg.sync()
            except SystemExit:
                raise
            except BaseException as e:
                qCritical(self.tr("Installation failed: ") + str(object=e))
                raise
            finally:
                self.progress_bar.emit(100)
                self.thread().quit()

        def _copy_dir(self, src: str, dst: str, /) -> None:
            for info in QDir(path=src).entryInfoList(
                filters=QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot
            ):
                target: str = QDir(path=dst).filePath(info.fileName())
                if info.isDir():
                    if "translations/setup" in info.absoluteFilePath():
                        continue
                    if not QDir().mkpath(target):
                        raise OSError("Create directory failed: " + target)
                    self._copy_dir(info.absoluteFilePath(), target)
                elif info.fileName().endswith(".exe") and info.dir() == QDir(
                    path=globals()["__compiled__"].python_runtime_dir
                ):
                    qInfo(
                        self.tr("Copying file: ")
                        + QDir(path=dst).filePath("SoundSplitter.exe")
                    )
                    if not QFile.copy(
                        info.absoluteFilePath(),
                        QDir(path=dst).filePath("SoundSplitter.exe"),
                    ):
                        raise OSError(
                            self.tr("Copy failed: ")
                            + QDir(path=dst).filePath("SoundSplitter.exe")
                        )
                    link(
                        src=QDir(path=dst).filePath("SoundSplitter.exe"),
                        dst=QDir(path=dst).filePath("uninstall.exe"),
                    )
                elif info.fileName().endswith(".lock"):
                    continue
                else:
                    qInfo(self.tr("Copying file: ") + info.absoluteFilePath())
                    if not QFile.copy(info.absoluteFilePath(), target):
                        raise OSError(self.tr("Copy failed: ") + target)

        def _link_dir(self, src: str, dst: str, /) -> None:
            dir_ = QDir()
            for info in QDir(path=src).entryInfoList(
                filters=QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot
            ):
                target: str = QDir(path=dst).filePath(info.fileName())
                if info.isDir():
                    if "translations/setup" in info.absoluteFilePath():
                        continue
                    if not dir_.mkpath(target):
                        raise OSError("Create directory failed: " + target)
                    self._link_dir(info.absoluteFilePath(), target)
                elif info.fileName().endswith(".exe") and info.dir() == QDir(
                    path=globals()["__compiled__"].python_runtime_dir
                ):
                    qInfo(
                        self.tr("Linking file: ")
                        + QDir(path=dst).filePath("SoundSplitter.exe")
                    )
                    link(
                        src=info.absoluteFilePath(),
                        dst=QDir(path=dst).filePath("SoundSplitter.exe"),
                    )
                    link(
                        src=info.absoluteFilePath(),
                        dst=QDir(path=dst).filePath("uninstall.exe"),
                    )
                elif info.fileName().endswith(".lock"):
                    continue
                else:
                    qInfo(self.tr("Linking file: ") + info.absoluteFilePath())
                    link(src=info.absoluteFilePath(), dst=target)

        def _rename_dir(self, src: str, dst: str, /) -> None:
            dir_ = QDir()
            for info in QDir(path=src).entryInfoList(
                filters=QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot
            ):
                target: str = QDir(path=dst).filePath(info.fileName())
                if info.isDir():
                    if not dir_.mkpath(target):
                        raise OSError("Create directory failed: " + target)
                    self._rename_dir(info.absoluteFilePath(), target)
                elif info.fileName().endswith(".lock"):
                    continue
                else:
                    qInfo(self.tr("Moving file: ") + info.absoluteFilePath())
                    file = QFile(info.absoluteFilePath())
                    if not file.rename(target):
                        qWarning(file.errorString())

        @staticmethod
        def _directory_size(directory: QDir, /) -> int:
            total_size = 0
            iterator = QDirIterator(
                directory.absolutePath(),
                QDir.Filter.Files | QDir.Filter.Hidden | QDir.Filter.System,
                flags=QDirIterator.IteratorFlag.Subdirectories,
            )
            while iterator.hasNext():
                iterator.next()
                total_size += iterator.fileInfo().size()
            return total_size // 1024

    def __init__(self) -> None:
        super().__init__()
        self._app = QApplication()
        self._wizard = QWizard()
        self._wizard.closeEvent = lambda event: event.ignore()
        self._wizard.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, on=False)
        self._ui = Ui_Wizard()
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
            self._lock = QLockFile(self._data_dir.absoluteFilePath("setup.lock"))
            self._lock.setStaleLockTime(0)
            if not self._lock.tryLock(0):
                if self._lock.error() == QLockFile.LockError.LockFailedError:
                    raise RuntimeError(
                        self.tr(
                            "The installer is already running. Please do not launch it again."
                        )
                    )
                else:
                    raise RuntimeError(
                        self.tr(
                            "Could not create the single-instance lock. Check the directory permissions."
                        )
                    )
            changeEvent_: Callable[[QEvent], None] = self._wizard.changeEvent

            def changeEvent(event: QEvent) -> None:
                match event.type():
                    case QEvent.Type.LanguageChange:
                        self._ui.retranslateUi(Wizard=self._wizard)
                        self._ui.welcomePage.setButtonText(
                            self._wizard.WizardButton.BackButton, self.tr("< &Back")
                        )
                        self._ui.welcomePage.setButtonText(
                            self._wizard.WizardButton.NextButton, self.tr("&Next >")
                        )
                        self._ui.welcomePage.setButtonText(
                            self._wizard.WizardButton.CancelButton, self.tr("Cancel")
                        )
                        self._ui.licensePage.setButtonText(
                            self._wizard.WizardButton.NextButton, self.tr("&Accept >")
                        )
                        changeEvent_(event)
                    case _:
                        changeEvent_(event)

            self._wizard.changeEvent = changeEvent
            translation_dir = QDir(
                path=globals()["__compiled__"].python_runtime_dir
                + "/translations/setup"
            )
            qt_path: str = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
            show_popup: Callable[[], None] = self._ui.languageComboBox.showPopup

            def showPopup() -> None:
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
                        locale_ = QLocale(file.removesuffix(".qm").replace("-", "_"))
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
                show_popup()

            self._ui.languageComboBox.showPopup = showPopup
            self._ui.languageComboBox.addItem("en_US")
            self._ui.languageComboBox.setCurrentIndex(
                self._ui.languageComboBox.count() - 1
            )
            self._ui.languageComboBox.activated.connect(
                self._on_language_combo_box_activated
            )
            license = QFile(":/text/LICENSE")
            if not license.open(QFile.OpenModeFlag.ReadOnly):
                raise RuntimeError(self.tr("Failed to open the license file."))
            self._ui.licenseTextBrowser.append(bytes(license.readAll().data()).decode())
            self._ui.licenseTextBrowser.moveCursor(QTextCursor.MoveOperation.Start)
            self._ui.licensePage.setButtonText(
                self._wizard.WizardButton.NextButton, self.tr("&Accept >")
            )
            self._ui.licenseCheckBox.toggled.connect(
                self._on_license_check_box_state_changed
            )
            self._ui.startMenuCheckBox.toggled.connect(
                lambda checked: setattr(Setup, "_start_menu", checked)
            )
            self._ui.desktopCheckBox.toggled.connect(
                lambda checked: setattr(Setup, "_desktop", checked)
            )
            self._ui.startupCheckBox.toggled.connect(
                lambda checked: setattr(Setup, "_startup", checked)
            )
            self._ui.InstallationTextBrowser.hide()
            self._ui.toolButton.toggled.connect(
                lambda checked: (
                    (
                        self._ui.InstallationTextBrowser.show(),
                        self._ui.toolButton.setText(self.tr("Show details")),
                    )
                    if checked
                    else (
                        self._ui.InstallationTextBrowser.hide(),
                        self._ui.toolButton.setText(self.tr("Hide details")),
                    )
                )
            )
            self._thread = QThread(parent=self._wizard)
            self._install = self._Install()
            self._install.moveToThread(self._thread)
            self._thread.started.connect(
                self._install.__call__, type=Qt.ConnectionType.QueuedConnection
            )
            self._install.progress_bar.connect(self._on_progress_bar)
            self._thread.finished.connect(self._on_thread_finished)
            self._wizard.currentIdChanged.connect(self._on_current_id_changed)
            self._ui.downloadPushButton.clicked.connect(
                lambda: QDesktopServices.openUrl("https://vb-audio.com/Cable/")
            )
            self._ui.homepageCheckBox.toggled.connect(
                self._on_homepage_check_box_toggled
            )
            self._ui.openCheckBox.toggled.connect(self._on_open_check_box_toggled)
            self._on_homepage_check_box_toggled(self._ui.homepageCheckBox.isChecked())
            self._on_open_check_box_toggled(self._ui.openCheckBox.isChecked())
        except SystemExit:
            raise
        except BaseException as e:
            self._on_critical(str(object=e))
            raise

    @Slot(int)
    def _on_current_id_changed(self, page_id: int, /) -> None:
        if page_id == self._wizard.pageIds()[1]:
            self._wizard.button(self._wizard.WizardButton.NextButton).setEnabled(
                self._ui.licenseCheckBox.isChecked()
            )
        elif page_id == self._wizard.pageIds()[3]:
            self._wizard.button(self._wizard.WizardButton.BackButton).setEnabled(False)
            self._wizard.button(self._wizard.WizardButton.NextButton).setEnabled(False)
            self._wizard.button(self._wizard.WizardButton.CancelButton).setEnabled(
                False
            )
            self._thread.start()
        elif page_id == self._wizard.pageIds()[4]:
            for device in QMediaDevices.audioOutputs():
                if "CABLE Input" in device.description():
                    self._ui.detectLabel.setText(self.tr("Detected"))
                    self._ui.detectLabel.setStyleSheet("color: rgb(40, 167, 69)")
                    self._ui.downloadPushButton.setEnabled(False)
                    break
            self._wizard.button(self._wizard.WizardButton.BackButton).setEnabled(False)

    @Slot(bool)
    def _on_license_check_box_state_changed(self, checked: bool, /) -> None:
        if self._wizard.currentId() == 1:
            self._wizard.button(self._wizard.WizardButton.NextButton).setEnabled(
                checked
            )

    @Slot(int)
    def _on_progress_bar(self, value: int, /) -> None:
        self._ui.progressBar.setValue(value)

    @Slot()
    def _on_thread_finished(self) -> None:
        self._thread.deleteLater()
        self._wizard.button(self._wizard.WizardButton.NextButton).setEnabled(True)

    @Slot(bool)
    def _on_homepage_check_box_toggled(self, checked: bool, /) -> None:
        if checked:
            self._homepage_conn: QMetaObject.Connection = self._wizard.button(
                self._wizard.WizardButton.FinishButton
            ).clicked.connect(
                lambda: QDesktopServices.openUrl(
                    "https://github.com/handsome-Druid/SoundSplitter"
                )
            )
        elif hasattr(self, "_homepage_conn"):
            self._wizard.button(
                self._wizard.WizardButton.FinishButton
            ).clicked.disconnect(self._homepage_conn)
            del self._homepage_conn

    @Slot(bool)
    def _on_open_check_box_toggled(self, checked: bool, /) -> None:
        if checked:
            self._open_conn: QMetaObject.Connection = self._wizard.button(
                self._wizard.WizardButton.FinishButton
            ).clicked.connect(
                lambda: QProcess.startDetached(
                    "explorer.exe",
                    arguments=(QDir.toNativeSeparators(self._executable),),
                )
            )
        elif hasattr(self, "_open_conn"):
            self._wizard.button(
                self._wizard.WizardButton.FinishButton
            ).clicked.disconnect(self._open_conn)
            del self._open_conn

    @Slot(str)
    def _on_critical(self, msg: str, /) -> None:
        self._ui.completeWidget.hide()
        self._ui.InstallationTextBrowser.append(self.tr("Critical: ") + msg)
        self._ui.completePage.setTitle(self.tr("Sound Splitter installation Failed"))
        QMessageBox.critical(
            self._wizard if hasattr(self, "_wizard") else None,
            self._app.applicationName(),
            self.tr("Critical: ") + msg,
        )

    def _message_handler(
        self, msg_type: QtMsgType, context: QMessageLogContext, msg: str
    ) -> None:
        if msg_type == QtMsgType.QtWarningMsg:
            if "QFont::setPointSize" in msg:
                return
            QMetaObject.invokeMethod(
                self._ui.InstallationTextBrowser,
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
                self._ui.InstallationTextBrowser,
                "append",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, msg),
            )

    def __call__(self) -> NoReturn:
        self._wizard.show()
        exit(self._app.exec())

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


def main() -> NoReturn:
    Setup()()
