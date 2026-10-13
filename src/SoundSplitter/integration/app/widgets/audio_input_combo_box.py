from typing import override

from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtWidgets import QComboBox


class AudioInputComboBox(QComboBox):
    @override
    def showPopup(self) -> None:
        current: str = self.currentText()
        self.clear()
        for device in QMediaDevices.audioInputs():
            self.addItem(device.description(), userData=device)
        index: int = self.findText(current)
        if index >= 0:
            self.setCurrentIndex(index)
        super().showPopup()
