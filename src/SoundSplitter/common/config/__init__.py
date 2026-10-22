from sys import platform
from typing import ClassVar, override

from pydantic import ConfigDict, ValidationError
from pydantic_yaml import (
    to_yaml_file,  # pyright: ignore[reportUnknownVariableType]
)
from PySide6.QtCore import (
    QCoreApplication,
    QDir,
    QFile,
    QFileInfo,
    QProcessEnvironment,
    QStandardPaths,
)
from PySide6.QtMultimedia import QAudioDevice, QMediaDevices
from PySide6.QtWidgets import QApplication

from .migration import V2, Migration


class Config(V2):
    model_config = ConfigDict(validate_assignment=True, from_attributes=True)
    tr: ClassVar[classmethod[Config, [str], str]] = classmethod(
        lambda cls, key: QCoreApplication.translate(cls.__name__, key)
    )

    @property
    def left_device(self) -> QAudioDevice | None:
        return next(
            (
                device
                for device in QMediaDevices.audioOutputs()
                if device.description() == self.left
            ),
            None,
        )

    @left_device.setter
    def left_device(self, value: QAudioDevice | None) -> None:
        self.left = value and value.description()

    @property
    def right_device(self) -> QAudioDevice | None:
        return next(
            (
                device
                for device in QMediaDevices.audioOutputs()
                if device.description() == self.right
            ),
            None,
        )

    @right_device.setter
    def right_device(self, value: QAudioDevice | None) -> None:
        self.right = value and value.description()

    @property
    def source_device(self) -> QAudioDevice | None:
        if self.loopback:
            return next(
                (
                    device
                    for device in QMediaDevices.audioOutputs()
                    if device.description() == self.source
                ),
                None,
            )
        return next(
            (
                device
                for device in QMediaDevices.audioInputs()
                if device.description() == self.source
            ),
            None,
        )

    @source_device.setter
    def source_device(self, value: QAudioDevice | None) -> None:
        self.source = value and value.description()

    @property
    def volume_device(self) -> QAudioDevice | None:
        return next(
            (
                device
                for device in QMediaDevices.audioOutputs()
                if device.description() == self.volume
            ),
            None,
        )

    @volume_device.setter
    def volume_device(self, value: QAudioDevice | None) -> None:
        self.volume = value and value.description()

    dir_: ClassVar[QDir]
    containing_dir: ClassVar[QDir]
    _file: ClassVar[QFile]

    @staticmethod
    def from_disk() -> Config:
        if "__compiled__" in globals():
            Config.containing_dir = QDir(globals()["__compiled__"].containing_dir)
        else:
            Config.containing_dir = QFileInfo(__file__).absoluteDir()
            for _ in range(4):
                if not Config.containing_dir.cdUp():
                    raise OSError(
                        f"cd {Config.containing_dir.path()}/../" + Config.tr(" failed.")
                    )
        app: QCoreApplication | None = QApplication.instance()
        assert app is not None
        if platform == "win32":
            path: str = (
                QProcessEnvironment.systemEnvironment().value("PROGRAMDATA")
                + "/"
                + app.applicationName()
            )
        else:
            if "__compiled__" in globals():
                path = "/var/lib/" + app.applicationName()
            else:
                path = QStandardPaths.writableLocation(
                    QStandardPaths.StandardLocation.AppLocalDataLocation
                )
        if not QDir().mkpath(path):
            raise OSError(
                Config.tr(
                    "Unable to create the required folder in the local data directory. "
                    "Please check permissions or available disk space."
                )
            )
        Config.dir_ = QDir(path)
        Config._file = QFile(Config.dir_.filePath("config.yml"))
        if Config._file.exists() and Config._file.size() > 0:
            return Config.model_validate(obj=Migration(Config._file.fileName()))
        config = Config()
        to_yaml_file(file=Config._file.fileName(), model=config)
        return config

    @override
    def __setattr__(self, name: str, value: object) -> None:
        if name not in type(self).model_fields:
            super().__setattr__(name, value)
            return
        old_value: object = getattr(self, name)
        try:
            super().__setattr__(name, value)
        except ValidationError:
            super().__setattr__(name, old_value)
            raise
        to_yaml_file(file=self._file.fileName(), model=self)
