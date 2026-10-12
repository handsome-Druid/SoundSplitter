from shutil import copytree
from sys import modules
from typing import override

from PySide6.QtCore import QCoreApplication, QDir, QLockFile, QStandardPaths, Slot, QObject, QFileInfo, QProcessEnvironment
from PySide6.QtWidgets import QApplication, QWizard

from .resources import resources_rc

modules["resources_rc"] = resources_rc

from .ui import Ui_Wizard


class Setup:
    tr: staticmethod[[str], str] = staticmethod(
        lambda key: QCoreApplication.translate(Setup.__name__, key)
    )
    class _Install(QObject):
        @override
        def __init__(self, /, application_name: str, parent: QObject | None = None, *, objectName: str | None = None) -> None:
            super().__init__(parent, objectName=objectName)
            self._application_name: str= application_name
        def __call__(self):
            application_dir = QDir(QProcessEnvironment.systemEnvironment().value("ProgramFiles")+ "/"+self._application_name)
            if not application_dir.removeRecursively():
                raise OSError(
                    self.tr(
                        "Failed to remove the existing installation directory."
                    )
                )
            if not application_dir.mkpath("."):
                raise OSError(
                    self.tr(
                        "Failed to create the installation directory."
                    )
                )
            
            
            copytree(src=QFileInfo(__file__).dir().absolutePath(), dst = )

    def __init__(self) -> None:
        self._app = QApplication()
        self._wizard = QWizard()
        self._ui = Ui_Wizard()
        self._ui.setupUi(Wizard=self._wizard)
        self._app.setApplicationName(self._wizard.windowTitle())
        if not QDir().mkpath(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppLocalDataLocation
            )
        ):
            raise OSError(
                self.tr(
                    "Unable to create the required folder in the local data directory. "
                    "Please check permissions or available disk space."
                )
            )
        self._lock = QLockFile(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppLocalDataLocation
            )
            + "/.setup.lock"
        )
        self._lock.setStaleLockTime(0)
        if not self._lock.tryLock(0):
            if self._lock.error() == QLockFile.LockError.LockFailedError:
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
        self._ui.licensePage.setButtonText(
            self._wizard.WizardButton.NextButton, self.tr("Accept(&A)")
        )
        self._ui.licenseCheckBox.toggled.connect(
            self._on_license_check_box_state_changed
        )
        self._ui.startMenuCheckBox.toggled.connect(
            lambda checked: setattr(self, "_start_menu", checked)
        )
        self._ui.desktopCheckBox.toggled.connect(
            lambda checked: setattr(self, "_desktop", checked)
        )

    @Slot(int)
    def _on_current_id_changed(self, page_id: int) -> None:
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

    @Slot(bool)
    def _on_license_check_box_state_changed(self, checked: bool) -> None:
        if self._wizard.currentId() == 1:
            self._wizard.button(self._wizard.WizardButton.NextButton).setEnabled(
                checked
            )
