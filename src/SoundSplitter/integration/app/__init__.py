from collections.abc import Callable, Collection
from configparser import ConfigParser
from io import StringIO
from sys import argv, exit, modules, platform
from types import TracebackType
from typing import NoReturn, Protocol, Self, cast

import pydantic._internal._validators  # noqa: F401
from pydantic import ValidationError
from PySide6.QtCore import (
    QCoreApplication,
    QDir,
    QEvent,
    QFile,
    QIODevice,
    QLibraryInfo,
    QLocale,
    QLockFile,
    QObject,
    QPoint,
    QRect,
    QSaveFile,
    QSettings,
    QSignalBlocker,
    QSize,
    QStandardPaths,
    Qt,
    QTimer,
    QTranslator,
    Slot,
)
from PySide6.QtGui import QAction, QCloseEvent, QCursor, QGuiApplication, QIcon, QScreen
from PySide6.QtMultimedia import QAudioDevice, QMediaDevices
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (
    QApplication,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
    QWidget,
)
from shiboken6 import isValid

from SoundSplitter.flow import Config, Start, Volume

from .resources import resources_rc

modules["resources_rc"] = resources_rc
from .ui import Ui_MainWindow


class APP:
    tr: classmethod[APP, [str], str] = classmethod(
        lambda cls, key: QCoreApplication.translate(cls.__name__, key)
    )

    class _DI(Protocol):
        def get[T](self, _: type[T], /) -> T: ...
        def close(self): ...
        def __enter__(self) -> Self: ...

    def __call__(self) -> NoReturn:
        if not self._hide:
            self._window.show()
            self._show_action.trigger()
        elif QSystemTrayIcon.isSystemTrayAvailable():
            self._hidden = getattr(self, "_hidden", set())
            self._hidden.add(self._window)
        else:
            self._window.showMinimized()
        exit(self._app.exec())

    def __init__(
        self,
        di: _DI,
        Logger: Callable[[str, QObject], QObject],
        /,
        *,
        main_window: QMainWindow | None = None,
    ) -> None:
        try:
            self._di: APP._DI = di
            if "--hide" in argv:
                argv.remove("--hide")
                self._hide = True
            else:
                self._hide = False
            self._app = QApplication(argv)
            self._app.aboutToQuit.connect(self._di.close)
            self._ui = Ui_MainWindow()
            self._window: QMainWindow = main_window or QMainWindow()
            self._ui.setupUi(MainWindow=self._window)
            self._message_box = QMessageBox(parent=self._window)
            self._app.setApplicationName(self._window.windowTitle())
            self._config: Config = self._di.get(Config)
            if not self._config.dir_.mkpath("logs"):
                raise OSError(
                    self.tr(
                        "Unable to create the log folder in the local data directory. Please check permissions or available disk space."
                    )
                )
            cast(QCoreApplication, self._app.instance()).installEventFilter(
                Logger(
                    self._config.dir_.absoluteFilePath(
                        "logs/" + self._app.applicationName() + ".log"
                    ),
                    self._window,
                )
            )
            if "__compiled__" in globals() and platform != "win32":
                self._lock = QLockFile("/run/" + self._app.applicationName() + "/.lock")
            else:
                self._lock = QLockFile(self._config.dir_.filePath(".lock"))
            self._lock.setStaleLockTime(0)
            if not self._lock.tryLock(0):
                if self._lock.error() == QLockFile.LockError.LockFailedError:
                    socket = QLocalSocket(parent=self._app)
                    socket.connectToServer(self._app.applicationName())
                    if socket.waitForConnected(msecs=500):
                        socket.write(b"SHOW")
                        if socket.waitForBytesWritten(msecs=500):
                            exit(0)
                    raise RuntimeError(
                        self.tr(
                            "Another instance is already running. Check the system tray."
                        )
                    )
                else:
                    raise RuntimeError(
                        self.tr(
                            "Could not create the single-instance lock. Check the directory permissions."
                        )
                    )
            self._di.__enter__()
            self._start: Start = self._di.get(Start)
            self._volume = Volume(parent=self._window)
            self._app.aboutToQuit.connect(
                lambda: self._volume.__exit__(None, None, None)
            )
            self._window.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, on=False)
            icon = QIcon(":/image/icon")
            self._tray_icon = QSystemTrayIcon(
                parent=self._window, toolTip=self._window.windowTitle(), icon=icon
            )
            self._tray_icon.activated.connect(self._on_tray_icon_activated)
            self._start_action = QAction(
                self._ui.startPushButton.text(), parent=self._window
            )
            self._start_action.triggered.connect(self._ui.startPushButton.click)
            self._stop_action = QAction(
                self._ui.stopPushButton.text(), parent=self._window
            )
            self._stop_action.triggered.connect(self._ui.stopPushButton.click)
            self._quit_action = QAction(self.tr("Exit"), parent=self._window)
            self._quit_action.triggered.connect(self._on_quit_action_triggered)
            self._show_action = QAction(
                self.tr("Show Main Window"), parent=self._window
            )
            self._show_action.triggered.connect(self._on_show_action_triggered)
            self._hide_action = QAction(self.tr("Hide to Tray"), parent=self._window)
            self._hide_action.triggered.connect(self._on_hide_action_triggered)
            self._tray_menu = QMenu(
                self._window.windowTitle(), parent=self._window, icon=icon
            )
            self._tray_menu.addActions((self._show_action, self._hide_action))
            self._tray_menu.addSeparator()
            self._tray_menu.addActions((self._start_action, self._stop_action))
            self._tray_menu.addSeparator()
            self._tray_menu.addAction(self._quit_action)
            self._tray_icon.setContextMenu(self._tray_menu)
            self._tray_icon.show()
            changeEvent_: Callable[[QEvent], None] = self._window.changeEvent

            def changeEvent(event: QEvent) -> None:
                match event.type():
                    case QEvent.Type.WindowStateChange if (
                        self._window.isMinimized()
                        and QSystemTrayIcon.isSystemTrayAvailable()
                    ):
                        self._hidden = getattr(self, "_hidden", set())
                        self._hidden.update(
                            widget
                            for widget in self._app.topLevelWidgets()
                            if widget.isVisible() and widget.hide() is None
                        )
                        event.accept()
                    case QEvent.Type.LanguageChange:
                        self._ui.retranslateUi(MainWindow=self._window)
                        self._start_action.setText(self._ui.startPushButton.text())
                        self._stop_action.setText(self._ui.stopPushButton.text())
                        self._quit_action.setText(self.tr("Exit"))
                        self._show_action.setText(self.tr("Show Main Window"))
                        self._hide_action.setText(self.tr("Hide to Tray"))
                        if self._ui.audioInputComboBox.currentData() is not None:
                            self._ui.sourceLabel.setText(
                                self.tr("Audio input source selected:")
                            )
                        changeEvent_(event)
                    case _:
                        changeEvent_(event)

            self._window.changeEvent = changeEvent
            closeEvent_: Callable[[QCloseEvent], None] = self._window.closeEvent

            def closeEvent(event: QCloseEvent) -> None:
                if (
                    self._message_box.question(
                        self._window,
                        self._app.applicationName(),
                        self.tr("Are you sure you want to exit?"),
                        buttons=self._message_box.StandardButton.Yes
                        | self._message_box.StandardButton.No,
                        defaultButton=self._message_box.StandardButton.No,
                    )
                    == self._message_box.StandardButton.Yes
                ):
                    closeEvent_(event)
                else:
                    event.ignore()

            self._window.closeEvent = closeEvent
            self._startup_command: str = '"' + argv[0] + '" --hide'
            if "__compiled__" in globals():
                if platform == "win32":
                    self._settings = QSettings(
                        r"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run",
                        QSettings.Format.NativeFormat,
                    )
                    if self._settings.contains(self._app.applicationName()):
                        self._ui.startupCheckBox.setChecked(True)
                        if (
                            self._settings.value(self._app.applicationName())
                            != self._startup_command
                        ):
                            self._settings.setValue(
                                self._app.applicationName(), self._startup_command
                            )
                    else:
                        self._ui.startupCheckBox.setChecked(False)
                if platform == "linux":
                    directory = QDir(
                        QStandardPaths.writableLocation(
                            QStandardPaths.StandardLocation.ConfigLocation
                        )
                    )
                    if not directory.mkpath("autostart"):
                        raise OSError("Cannot create autostart directory")
                    self._startup_file = QFile(
                        directory.absoluteFilePath("autostart/SoundSplitter.desktop")
                    )
                    if self._startup_file.exists():
                        self._ui.startupCheckBox.setChecked(True)
                self._ui.startupCheckBox.checkStateChanged.connect(
                    self._on_startup_check_box_check_state_changed
                )
            else:
                self._ui.startupCheckBox.setEnabled(False)
                self._ui.startupCheckBox.hide()
            show_popup: Callable[[], None] = self._ui.languageComboBox.showPopup
            translation_dir = QDir(
                path=self._config.containing_dir.filePath(
                    "translations/" + self._app.applicationName()
                )
            )
            qt_path: str = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)

            def showPopup() -> None:
                current: str = self._ui.languageComboBox.currentText()
                self._ui.languageComboBox.clear()
                self._ui.languageComboBox.addItem("en_US")
                for file in translation_dir.entryList(
                    ["*.qm"], filters=QDir.Filter.Files
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
            for file in translation_dir.entryList(["*.qm"], filters=QDir.Filter.Files):
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
                if (
                    locale is not None and locale.name() == self._config.language
                ) or file == self._config.language:
                    if locale is not None:
                        qt_translator = QTranslator()
                        if qt_translator.load(locale, "qtbase", "_", directory=qt_path):
                            self._app.installTranslator(qt_translator)
                        else:
                            qt_translator = None
                    else:
                        qt_translator = None
                    self._app.installTranslator(translator)
                    self._translators = (qt_translator, translator)
                    self._ui.languageComboBox.addItem(
                        locale.name() if locale is not None else file, self._translators
                    )
                    self._ui.languageComboBox.setCurrentIndex(
                        self._ui.languageComboBox.count() - 1
                    )
                    break
            self._ui.languageComboBox.activated.connect(
                self._on_language_combo_box_activated
            )

            self._ui.leftToolButton.setIconSize(QSize(20, 16))
            self._ui.rightToolButton.setIconSize(QSize(20, 16))
            self._ui.leftHorizontalSlider.valueChanged.connect(
                lambda value: setattr(self._volume, "left_volume_percent", value)
            )
            self._ui.rightHorizontalSlider.valueChanged.connect(
                lambda value: setattr(self._volume, "right_volume_percent", value)
            )
            self._ui.leftHorizontalSlider.valueChanged.connect(
                lambda value: self._ui.leftToolButton.setIcon(
                    self._volume_0
                    if value < 1
                    else self._volume_1
                    if value < 33
                    else self._volume_2
                    if value < 66
                    else self._volume_3
                )
            )
            self._ui.rightHorizontalSlider.valueChanged.connect(
                lambda value: self._ui.rightToolButton.setIcon(
                    self._volume_0
                    if value < 1
                    else self._volume_1
                    if value < 33
                    else self._volume_2
                    if value < 66
                    else self._volume_3
                )
            )
            self._ui.leftHorizontalSlider.valueChanged.connect(
                lambda value: self._ui.leftVolumeLabel.setText(f"{value}%")
            )
            self._ui.rightHorizontalSlider.valueChanged.connect(
                lambda value: self._ui.rightVolumeLabel.setText(f"{value}%")
            )
            self._ui.leftHorizontalSlider.valueChanged.connect(
                self._ui.leftToolButton.setChecked
            )
            self._ui.rightHorizontalSlider.valueChanged.connect(
                self._ui.rightToolButton.setChecked
            )
            self._ui.leftHorizontalSlider.sliderReleased.connect(
                lambda: (
                    self._ui.leftHorizontalSlider.setValue(
                        round(number=self._volume.left_volume_percent)
                    ),
                    self._ui.leftToolButton.setChecked(not self._volume.left_mute),
                )
            )
            self._ui.rightHorizontalSlider.sliderReleased.connect(
                lambda: (
                    self._ui.rightHorizontalSlider.setValue(
                        round(number=self._volume.right_volume_percent)
                    ),
                    self._ui.rightToolButton.setChecked(not self._volume.right_mute),
                )
            )
            self._ui.leftToolButton.toggled.connect(self._on_left_tool_button_toggled)
            self._ui.rightToolButton.toggled.connect(self._on_right_tool_button_toggled)
            self._volume.left_notify.connect(self._on_volume_left_notify)
            self._volume.right_notify.connect(self._on_volume_right_notify)
            self._start.finished.connect(self._on_start_finished)
            self._ui.startPushButton.setEnabled(True)
            self._ui.stopPushButton.setEnabled(False)
            self._ui.startPushButton.clicked.connect(self._on_start_push_button_clicked)
            self._ui.stopPushButton.clicked.connect(self._on_stop_push_button_clicked)
            self._ui.refreshPushButton.clicked.connect(
                self._on_refresh_push_button_clicked
            )
            self._ui.leftListWidget.currentItemChanged.connect(
                self.on_left_list_widget_current_item_changed
            )
            self._ui.rightListWidget.currentItemChanged.connect(
                self.on_right_list_widget_current_item_changed
            )
            audio_input_show_popup: Callable[[], None] = (
                self._ui.audioInputComboBox.showPopup
            )

            def _showPopup() -> None:
                current: str = self._ui.audioInputComboBox.currentText()
                self._ui.audioInputComboBox.clear()
                for device in (
                    QMediaDevices.audioOutputs()
                    if self._config.loopback
                    else QMediaDevices.audioInputs()
                ):
                    self._ui.audioInputComboBox.addItem(
                        device.description(), userData=device
                    )
                index: int = self._ui.audioInputComboBox.findText(current)
                if index >= 0:
                    self._ui.audioInputComboBox.setCurrentIndex(index)
                audio_input_show_popup()

            self._ui.audioInputComboBox.showPopup = _showPopup
            self._ui.audioInputComboBox.activated.connect(
                self._on_audio_input_combo_box_activated
            )
            self._ui.leftSpinBox.setValue(self._config.left_latency_ms)
            self._ui.rightSpinBox.setValue(self._config.right_latency_ms)
            self._ui.leftSpinBox.valueChanged.connect(
                self._on_left_spin_box_value_changed
            )
            self._ui.rightSpinBox.valueChanged.connect(
                self._on_right_spin_box_value_changed
            )
            self._mediadevices = QMediaDevices(parent=self._window)
            self._ui.audioOutputComboBox.setEnabled(False)
            self._ui.audioOutputComboBox.currentTextChanged.connect(
                self._on_audio_output_combo_box_current_text_changed
            )
            self._ui.loopbackCheckBox.toggled.connect(
                self._on_loopback_check_box_toggled
            )
            self._ui.monitorCheckBox.setChecked(False)
            self._ui.monitorCheckBox.checkStateChanged.connect(
                self._on_check_box_check_state_changed
            )
            if platform == "linux":
                self._ui.loopbackCheckBox.setChecked(True)
                self._on_loopback_check_box_toggled(True)
                self._config.volume = self._config.source = (
                    "CABLE Input (SoundSplitter)"
                )
                self._ui.loopbackCheckBox.hide()
            else:
                self._ui.loopbackCheckBox.setChecked(self._config.loopback)
            self._mediadevices.audioInputsChanged.connect(self._on_audio_device_changed)
            self._mediadevices.audioOutputsChanged.connect(
                self._on_audio_device_changed
            )
            if self._config.volume_device is not None:
                assert self._config.volume is not None
                self._ui.monitorCheckBox.setChecked(True)
                self._ui.audioOutputComboBox.addItem(
                    self._config.volume, userData=self._config.volume_device
                )
                self._ui.audioOutputComboBox.setCurrentIndex(
                    self._ui.audioOutputComboBox.count() - 1
                )
            if self._config.source_device is not None:
                self._ui.audioInputComboBox.addItem(
                    self._config.source_device.description(),
                    userData=self._config.source_device,
                )
                self._ui.audioInputComboBox.setCurrentIndex(
                    self._ui.audioInputComboBox.count() - 1
                )
                self._ui.sourceLabel.setText(self.tr("Audio input source selected:"))
                self._ui.sourceLabel.setStyleSheet("color: rgb(40, 167, 69)")
            else:
                for device in self._mediadevices.audioInputs():
                    description: str = device.description()
                    if "CABLE Output" in device.description():
                        self._ui.audioInputComboBox.addItem(
                            description, userData=device
                        )
                        self._ui.audioInputComboBox.setCurrentIndex(
                            self._ui.audioInputComboBox.count() - 1
                        )
                        self._ui.sourceLabel.setText(
                            self.tr("Audio input source selected:")
                        )
                        self._ui.sourceLabel.setStyleSheet("color: rgb(40, 167, 69)")
                        self._config.volume_device = self._config.source_device = device
                        break
            if (
                self._config.source is not None
                and not self._ui.monitorCheckBox.isChecked()
                and "CABLE Output" in self._config.source
            ):
                for device in self._mediadevices.audioOutputs():
                    description: str = device.description()
                    if "CABLE Input" in device.description():
                        self._ui.monitorCheckBox.setChecked(True)
                        self._config.volume_device = device
                        break
            self._ui.refreshPushButton.click()
            self._server = QLocalServer(parent=self._app)
            self._server.newConnection.connect(self._on_new_connection)
            QLocalServer.removeServer(self._app.applicationName())
            if not self._server.listen(self._app.applicationName()):
                raise RuntimeError(self._server.errorString())
            if platform == "win32":
                from ctypes import windll  # pyright: ignore[reportAttributeAccessIssue]

                if windll.shell32.IsUserAnAdmin():
                    self._pending_msg: list[str] = getattr(self, "_pending_msg", [])
                    self._pending_msg.append(
                        self.tr("Do not run SoundSplitter as administrator.")
                    )
                else:
                    self._ui.startPushButton.click()
            else:
                self._ui.startPushButton.click()
        except BaseException as e:
            if isinstance(e, SystemExit) and e.code == 0:
                raise
            getattr(self, "_message_box", QMessageBox).critical(
                getattr(self, "_window", None),
                self._app.applicationName() if hasattr(self, "_app") else "Critical",
                str(e),
            )
            raise

    @Slot(object, object, object)
    def _on_start_finished(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._ui.startPushButton.setEnabled(True)
        self._ui.refreshPushButton.setEnabled(True)
        self._ui.leftListWidget.setEnabled(True)
        self._ui.rightListWidget.setEnabled(True)
        self._ui.leftSpinBox.setEnabled(True)
        self._ui.rightSpinBox.setEnabled(True)
        self._ui.audioInputComboBox.setEnabled(True)
        if self._ui.loopbackCheckBox.isChecked():
            self._ui.monitorCheckBox.setEnabled(False)
        else:
            self._ui.monitorCheckBox.setEnabled(True)
            if self._ui.monitorCheckBox.isChecked():
                self._ui.audioOutputComboBox.setEnabled(True)
            else:
                self._ui.audioOutputComboBox.setEnabled(False)
        self._ui.loopbackCheckBox.setEnabled(True)
        self._ui.stopPushButton.setEnabled(False)
        self._start_action.setEnabled(True)
        self._stop_action.setEnabled(False)
        if exc_type is not None:
            if self._window.isVisible():
                box = QMessageBox(
                    QMessageBox.Icon.Critical,
                    self._app.applicationName(),
                    str(object=exc) if exc is not None else str(object=exc_type),
                    buttons=QMessageBox.StandardButton.Ok,
                    parent=self._window,
                )
                self._message_boxes: set[QMessageBox] = getattr(
                    self, "_message_boxes", set()
                )
                self._message_boxes.add(box)
                box.finished.connect(
                    lambda: getattr(self, "_message_boxes", set()).discard(box)
                )
                box.finished.connect(
                    lambda: getattr(self, "_hidden", set()).discard(box)
                )
                box.finished.connect(box.deleteLater)
                box.open()
            else:
                self._pending_msg: list[str] = getattr(self, "_pending_msg", [])
                self._pending_msg.append(str(object=exc))

    @Slot()
    def _on_start_push_button_clicked(self) -> None:
        self._ui.startPushButton.setEnabled(False)
        self._start(None, None, None)
        self._ui.refreshPushButton.setEnabled(False)
        self._ui.leftListWidget.setEnabled(False)
        self._ui.rightListWidget.setEnabled(False)
        self._ui.leftSpinBox.setEnabled(False)
        self._ui.rightSpinBox.setEnabled(False)
        self._ui.audioInputComboBox.setEnabled(False)
        self._ui.audioOutputComboBox.setEnabled(False)
        self._ui.monitorCheckBox.setEnabled(False)
        self._ui.loopbackCheckBox.setEnabled(False)
        self._ui.stopPushButton.setEnabled(True)
        self._start_action.setEnabled(False)
        self._stop_action.setEnabled(True)
        self._started = True

    @Slot()
    def _on_stop_push_button_clicked(self) -> None:
        self._start.__exit__(None, None, None)
        self._started = False

    @Slot()
    def _on_refresh_push_button_clicked(self) -> None:
        self._ui.leftListWidget.setCurrentRow(-1)
        self._ui.rightListWidget.setCurrentRow(-1)
        self._ui.leftListWidget.clear()
        self._ui.rightListWidget.clear()
        for device in self._mediadevices.audioOutputs():
            for name in ("left", "right"):
                description: str = device.description()
                item = QListWidgetItem(description)
                item.setData(Qt.ItemDataRole.UserRole, device)
                list_widget: QListWidget = getattr(self._ui, name + "ListWidget")
                list_widget.addItem(item)
                if description == getattr(self._config, name):
                    list_widget.setCurrentItem(item)

    @Slot()
    def _on_audio_input_combo_box_activated(self) -> None:
        device: QAudioDevice = self._ui.audioInputComboBox.currentData(
            Qt.ItemDataRole.UserRole
        )
        self._config.source_device = device
        self._ui.sourceLabel.setText(self.tr("Audio input source selected:"))
        self._ui.sourceLabel.setStyleSheet("color: rgb(40, 167, 69)")
        if "CABLE Output" in device.description():
            for device in self._mediadevices.audioOutputs():
                if "CABLE Input" in device.description():
                    self._config.volume_device = device
                    self._ui.monitorCheckBox.setChecked(True)
                    self._ui.audioOutputComboBox.clear()
                    self._ui.audioOutputComboBox.addItem(
                        device.description(), userData=device
                    )
                    self._ui.audioOutputComboBox.setCurrentIndex(
                        self._ui.audioOutputComboBox.count() - 1
                    )
                    break
        if self._ui.loopbackCheckBox.isChecked():
            self._ui.audioOutputComboBox.clear()
            self._ui.audioOutputComboBox.addItem(device.description(), userData=device)
            self._ui.audioOutputComboBox.setCurrentIndex(0)

    @Slot(QListWidgetItem, QListWidgetItem)
    def on_left_list_widget_current_item_changed(
        self,
        current: QListWidgetItem | None,
        previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            return
        device: QAudioDevice = current.data(Qt.ItemDataRole.UserRole)
        try:
            self._config.left_device = device
            self._volume.left = device.description()
            self._ui.leftHorizontalSlider.setValue(
                round(number=self._volume.left_volume_percent)
            )
            self._ui.leftToolButton.setChecked(not self._volume.left_mute)
        except ValidationError as e:
            if self._window.isVisible():
                box = QMessageBox(
                    QMessageBox.Icon.Critical,
                    self._app.applicationName(),
                    str(object=e),
                    buttons=QMessageBox.StandardButton.Ok,
                    parent=self._window,
                )
                self._message_boxes = getattr(self, "_message_boxes", set())
                self._message_boxes.add(box)
                box.finished.connect(
                    lambda: getattr(self, "_message_boxes", set()).discard(box)
                )
                box.finished.connect(
                    lambda: getattr(self, "_hidden", set()).discard(box)
                )
                box.finished.connect(box.deleteLater)
                box.open()
            else:
                self._pending_msg: list[str] = getattr(self, "_pending_msg", [])
                self._pending_msg.append(str(object=e))
            QTimer.singleShot(
                0,
                lambda: (
                    self._ui.leftListWidget.setCurrentRow(-1)
                    if previous is None
                    else self._ui.leftListWidget.setCurrentItem(previous)
                ),
            )

    @Slot(QListWidgetItem, QListWidgetItem)
    def on_right_list_widget_current_item_changed(
        self,
        current: QListWidgetItem | None,
        previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            return
        device: QAudioDevice = current.data(Qt.ItemDataRole.UserRole)
        try:
            self._config.right_device = device
            self._volume.right = device.description()
            self._ui.rightHorizontalSlider.setValue(
                round(number=self._volume.right_volume_percent)
            )
            self._ui.rightToolButton.setChecked(not self._volume.right_mute)
        except ValidationError as e:
            if self._window.isVisible():
                box = QMessageBox(
                    QMessageBox.Icon.Critical,
                    self._app.applicationName(),
                    str(object=e),
                    buttons=QMessageBox.StandardButton.Ok,
                    parent=self._window,
                )
                self._message_boxes = getattr(self, "_message_boxes", set())
                self._message_boxes.add(box)
                box.finished.connect(
                    lambda: getattr(self, "_message_boxes", set()).discard(box)
                )
                box.finished.connect(
                    lambda: getattr(self, "_hidden", set()).discard(box)
                )
                box.finished.connect(box.deleteLater)
                box.open()
            else:
                self._pending_msg: list[str] = getattr(self, "_pending_msg", [])
                self._pending_msg.append(str(object=e))
            QTimer.singleShot(
                0,
                lambda: (
                    self._ui.rightListWidget.setCurrentRow(-1)
                    if previous is None
                    else self._ui.rightListWidget.setCurrentItem(previous)
                ),
            )

    @Slot(Qt.CheckState)
    def _on_check_box_check_state_changed(self, state: Qt.CheckState) -> None:
        if state == Qt.CheckState.Checked:
            self._ui.audioOutputComboBox.setEnabled(True)
            source_device: QAudioDevice | None = self._config.source_device
            if (
                source_device is not None
                and "CABLE Output" in source_device.description()
            ):
                for device in self._mediadevices.audioOutputs():
                    if "CABLE Input" in device.description():
                        self._config.volume_device = device
                        self._ui.audioOutputComboBox.clear()
                        self._ui.audioOutputComboBox.addItem(
                            device.description(), userData=device
                        )
                        self._ui.audioOutputComboBox.setCurrentIndex(
                            self._ui.audioOutputComboBox.count() - 1
                        )
                        break
        else:
            self._ui.audioOutputComboBox.setCurrentIndex(-1)
            self._ui.audioOutputComboBox.setEnabled(False)
            self._config.volume_device = None

    @Slot()
    def _on_audio_output_combo_box_current_text_changed(self) -> None:
        self._config.volume_device = self._ui.audioOutputComboBox.currentData(
            Qt.ItemDataRole.UserRole
        )

    @Slot(QSystemTrayIcon.ActivationReason)
    def _on_tray_icon_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_action.trigger()

    @Slot()
    def _on_hide_action_triggered(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self._window.showMinimized()
            return
        self._hidden: set[QWidget] = getattr(self, "_hidden", set())
        self._hidden.update(
            widget
            for widget in self._app.topLevelWidgets()
            if widget.isVisible() and widget.hide() is None
        )

    @Slot()
    def _on_show_action_triggered(self) -> None:
        if self._window.isMinimized():
            self._window.showNormal()
        if hasattr(self, "_hidden"):
            for widget in self._hidden:
                if isValid(widget):
                    widget.show()
            del self._hidden
        screen: QScreen = (
            QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        )
        available: QRect = screen.availableGeometry()
        center: QPoint = screen.availableGeometry().center()
        for window in self._app.topLevelWidgets():
            if window.isVisible() and not available.contains(window.frameGeometry()):
                window.move(center - window.frameGeometry().center() + window.pos())
        self._window.raise_()
        self._window.activateWindow()
        modal: QWidget | None = self._app.activeModalWidget()
        if hasattr(self, "_pending_msg"):
            box = QMessageBox(
                QMessageBox.Icon.Critical,
                self._app.applicationName(),
                "\n".join(self._pending_msg),
                buttons=QMessageBox.StandardButton.Ok,
                parent=self._window,
            )
            self._message_boxes = getattr(self, "_message_boxes", set())
            self._message_boxes.add(box)
            box.finished.connect(
                lambda: getattr(self, "_message_boxes", set()).discard(box)
            )
            box.finished.connect(lambda: getattr(self, "_hidden", set()).discard(box))
            box.finished.connect(box.deleteLater)
            del self._pending_msg
            box.finished.connect(
                lambda: (
                    (modal.raise_(), modal.activateWindow())
                    if (modal := self._app.activeModalWidget()) is not None
                    else None
                )
            )
            box.open()
        elif modal is not None:
            modal.raise_()
            modal.activateWindow()

    @Slot()
    def _on_quit_action_triggered(self) -> None:
        self._window.hide()
        self._app.quit()

    @Slot()
    def _on_audio_device_changed(self) -> None:
        if (
            not getattr(self, "_started", False)
            or not self._ui.startPushButton.isEnabled()
        ):
            return
        if (
            self._config.source_device is not None
            and self._config.left_device is not None
            and self._config.right_device is not None
        ):
            self._hidden = getattr(self, "_hidden", set())
            if hasattr(self, "_message_boxes"):
                for box in self._message_boxes.copy():
                    box.close()
                    box.deleteLater()
                    self._hidden.discard(box)
                del self._message_boxes
            if hasattr(self, "_pending_msg"):
                del self._pending_msg
            self._ui.startPushButton.click()

    @Slot(Qt.CheckState)
    def _on_startup_check_box_check_state_changed(self, state: Qt.CheckState) -> None:
        if state == Qt.CheckState.Checked:
            if platform == "win32":
                self._settings.setValue(
                    self._app.applicationName(), self._startup_command
                )
            if platform == "linux":
                directory = QDir(
                    path=QStandardPaths.writableLocation(
                        QStandardPaths.StandardLocation.ConfigLocation
                    )
                )
                if not directory.mkpath("autostart"):
                    raise OSError("Cannot create autostart directory")
                executable: str = QCoreApplication.applicationFilePath()
                exec_command: str = (
                    executable.replace("\\", "\\\\\\\\")
                    .replace('"', '\\\\"')
                    .replace("`", "\\\\`")
                    .replace("$", "\\\\$")
                    .replace("%", "%%")
                )

                settings = ConfigParser(interpolation=None)
                settings.optionxform = lambda optionstr: optionstr
                settings["Desktop Entry"] = {
                    "Type": "Application",
                    "Name": "SoundSplitter",
                    "Exec": f'"{exec_command}" --hide',
                    "TryExec": executable,
                    "Terminal": "false",
                }
                with StringIO() as buffer:
                    settings.write(fp=buffer, space_around_delimiters=False)
                    content: bytes = buffer.getvalue().encode()
                file = QSaveFile(self._startup_file.fileName())
                if not file.open(QIODevice.OpenModeFlag.WriteOnly):
                    raise OSError(file.errorString())
                if file.write(content) != len(content):
                    error: str = file.errorString()
                    file.cancelWriting()
                    raise OSError(error)
                if not file.commit():
                    raise OSError(file.errorString())
        else:
            if platform == "win32":
                self._settings.remove(self._app.applicationName())
            if platform == "linux":
                if self._startup_file.exists() and not self._startup_file.remove():
                    raise OSError(self._startup_file.errorString())

    @Slot(int)
    def _on_left_spin_box_value_changed(self, value: int) -> None:
        try:
            self._config.left_latency_ms = value
        except ValidationError as e:
            if self._window.isVisible():
                box = QMessageBox(
                    QMessageBox.Icon.Critical,
                    self._app.applicationName(),
                    str(object=e),
                    buttons=QMessageBox.StandardButton.Ok,
                    parent=self._window,
                )
                self._message_boxes = getattr(self, "_message_boxes", set())
                self._message_boxes.add(box)
                box.finished.connect(
                    lambda: getattr(self, "_message_boxes", set()).discard(box)
                )
                box.finished.connect(
                    lambda: getattr(self, "_hidden", set()).discard(box)
                )
                box.finished.connect(box.deleteLater)
                box.open()
            else:
                self._pending_msg: list[str] = getattr(self, "_pending_msg", [])
                self._pending_msg.append(str(object=e))
            QTimer.singleShot(
                0, lambda: self._ui.leftSpinBox.setValue(self._config.left_latency_ms)
            )

    @Slot(int)
    def _on_right_spin_box_value_changed(self, value: int) -> None:
        try:
            self._config.right_latency_ms = value
        except ValidationError as e:
            if self._window.isVisible():
                box = QMessageBox(
                    QMessageBox.Icon.Critical,
                    self._app.applicationName(),
                    str(object=e),
                    buttons=QMessageBox.StandardButton.Ok,
                    parent=self._window,
                )
                self._message_boxes = getattr(self, "_message_boxes", set())
                self._message_boxes.add(box)
                box.finished.connect(
                    lambda: getattr(self, "_message_boxes", set()).discard(box)
                )
                box.finished.connect(
                    lambda: getattr(self, "_hidden", set()).discard(box)
                )
                box.finished.connect(box.deleteLater)
                box.open()
            else:
                self._pending_msg: list[str] = getattr(self, "_pending_msg", [])
                self._pending_msg.append(str(object=e))
            QTimer.singleShot(
                0, lambda: self._ui.rightSpinBox.setValue(self._config.right_latency_ms)
            )

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
        self._config.language = self._ui.languageComboBox.currentText()

    _volume_1 = QIcon()
    _volume_1.addFile(
        ":/image/volume-1.svg", mode=QIcon.Mode.Normal, state=QIcon.State.On
    )
    _volume_1.addFile(
        ":/image/volume-x.svg", mode=QIcon.Mode.Normal, state=QIcon.State.Off
    )
    _volume_2 = QIcon()
    _volume_2.addFile(
        ":/image/volume-2.svg", mode=QIcon.Mode.Normal, state=QIcon.State.On
    )
    _volume_2.addFile(
        ":/image/volume-x.svg", mode=QIcon.Mode.Normal, state=QIcon.State.Off
    )
    _volume_3 = QIcon()
    _volume_3.addFile(
        ":/image/volume-3.svg", mode=QIcon.Mode.Normal, state=QIcon.State.On
    )
    _volume_3.addFile(
        ":/image/volume-x.svg", mode=QIcon.Mode.Normal, state=QIcon.State.Off
    )
    _volume_0 = QIcon()
    _volume_0.addFile(
        ":/image/volume.svg", mode=QIcon.Mode.Normal, state=QIcon.State.On
    )
    _volume_0.addFile(
        ":/image/volume-x.svg", mode=QIcon.Mode.Normal, state=QIcon.State.Off
    )

    @Slot(object)
    def _on_volume_left_notify(self, value: float | bool) -> None:
        if self._ui.leftHorizontalSlider.isSliderDown():
            return
        if isinstance(value, bool):
            self._ui.leftToolButton.setChecked(value)
        else:
            volume_percent: float = round(number=value * 100.0)
            self._ui.leftVolumeLabel.setText(f"{volume_percent}%")
            with QSignalBlocker(self._ui.leftHorizontalSlider):
                self._ui.leftHorizontalSlider.setValue(volume_percent)
            if volume_percent < 1:
                self._ui.leftToolButton.setIcon(self._volume_0)
            elif volume_percent < 33:
                self._ui.leftToolButton.setIcon(self._volume_1)
            elif volume_percent < 66:
                self._ui.leftToolButton.setIcon(self._volume_2)
            else:
                self._ui.leftToolButton.setIcon(self._volume_3)
            QTimer.singleShot(0, lambda: self._ui.leftToolButton.setChecked(True))

    @Slot(object)
    def _on_volume_right_notify(self, value: float | bool) -> None:
        if self._ui.rightHorizontalSlider.isSliderDown():
            return
        if isinstance(value, bool):
            self._ui.rightToolButton.setChecked(value)
        else:
            volume_percent: float = round(number=value * 100.0)
            self._ui.rightVolumeLabel.setText(f"{volume_percent}%")
            with QSignalBlocker(self._ui.rightHorizontalSlider):
                self._ui.rightHorizontalSlider.setValue(volume_percent)
            if volume_percent < 1:
                self._ui.rightToolButton.setIcon(self._volume_0)
            elif volume_percent < 33:
                self._ui.rightToolButton.setIcon(self._volume_1)
            elif volume_percent < 66:
                self._ui.rightToolButton.setIcon(self._volume_2)
            else:
                self._ui.rightToolButton.setIcon(self._volume_3)
            QTimer.singleShot(0, lambda: self._ui.rightToolButton.setChecked(True))

    @Slot(bool)
    def _on_left_tool_button_toggled(self, checked: bool) -> None:
        volume_percent: float = round(number=self._volume.left_volume_percent)
        if volume_percent < 1:
            self._ui.leftToolButton.setIcon(self._volume_0)
        elif volume_percent < 33:
            self._ui.leftToolButton.setIcon(self._volume_1)
        elif volume_percent < 66:
            self._ui.leftToolButton.setIcon(self._volume_2)
        else:
            self._ui.leftToolButton.setIcon(self._volume_3)
        self._volume.left_mute = not checked

    @Slot(bool)
    def _on_right_tool_button_toggled(self, checked: bool) -> None:
        volume_percent: float = round(number=self._volume.right_volume_percent)
        if volume_percent < 1:
            self._ui.rightToolButton.setIcon(self._volume_0)
        elif volume_percent < 33:
            self._ui.rightToolButton.setIcon(self._volume_1)
        elif volume_percent < 66:
            self._ui.rightToolButton.setIcon(self._volume_2)
        else:
            self._ui.rightToolButton.setIcon(self._volume_3)
        self._volume.right_mute = not checked

    @Slot()
    def _on_new_connection(self) -> None:
        socket: QLocalSocket = self._server.nextPendingConnection()

        @Slot()
        def on_ready_read() -> None:
            while socket.bytesAvailable() >= 4:
                match socket.read(4).data():
                    case b"SHOW":
                        self._show_action.trigger()
                    case b"EXIT":
                        self._window.hide()
                        self._app.quit()
                    case _:
                        pass
                socket.disconnectFromServer()

        socket.readyRead.connect(on_ready_read)

    @Slot(bool)
    def _on_loopback_check_box_toggled(self, checked: bool) -> None:
        self._config.loopback = checked
        if self._config.source_device is None:
            self._ui.audioInputComboBox.clear()
            self._config.source = None
        if checked:
            self._ui.monitorCheckBox.setChecked(True)
            self._ui.audioOutputComboBox.clear()
            self._ui.audioOutputComboBox.addItem(
                self._ui.audioInputComboBox.currentText(),
                userData=self._ui.audioInputComboBox.currentData(
                    Qt.ItemDataRole.UserRole
                ),
            )
            self._ui.audioOutputComboBox.setCurrentIndex(0)
        self._ui.monitorCheckBox.setDisabled(checked)
        self._ui.audioOutputComboBox.setDisabled(checked)
