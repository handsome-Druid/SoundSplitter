from collections.abc import Generator
from json import dumps
from os import environ
from sys import platform

from ashka import AshkaScope
from dishka import (
    BaseScope,
    Container,
    Provider,
    Scope,
    make_container,
    provide,  # pyright: ignore[reportUnknownVariableType]
)
from dishka.dependency_source import CompositeDependencySource
from PySide6.QtCore import QEventLoop, QProcess, QTimer
from PySide6.QtMultimedia import QMediaDevices

from SoundSplitter.flow import Config, Start


class DI:
    class _Provider(Provider):
        scope: BaseScope | None = Scope.APP
        _config: CompositeDependencySource = provide(
            source=staticmethod(Config.from_disk), provides=Config
        )

        @provide
        @staticmethod
        def _start(config: Config) -> Generator[Start]:
            with Start(config) as start:
                yield start

        if platform == "linux":

            @provide(scope=AshkaScope.BOOTSTRAP)
            @staticmethod
            def _cable() -> Generator[None]:
                environ["PIPEWIRE_PROPS"] = (
                    "{ "
                    + environ.get(key="PIPEWIRE_PROPS", default="")
                    .strip()
                    .removeprefix("{")
                    .removesuffix("}")
                    + " jack.show-monitor=true jack.merge-monitor=true "
                    + "jack.short-name=false jack.filter-name=true jack.filter-char=_ "
                    + "node.dont-move=true }"
                )
                name = "CABLE Input (SoundSplitter)"
                process = QProcess()
                devices = QMediaDevices()
                loop = QEventLoop()
                timeout = QTimer(singleShot=True)

                devices.audioOutputsChanged.connect(
                    lambda: (
                        any(
                            device.description() == name
                            for device in devices.audioOutputs()
                        )
                        and loop.quit()
                    )
                )
                process.finished.connect(loop.quit)
                timeout.timeout.connect(loop.quit)
                try:
                    process.start(
                        "pw-cli",
                        arguments=[
                            "-m",
                            "create-node",
                            "adapter",
                            dumps(
                                obj={
                                    "factory.name": "support.null-audio-sink",
                                    "node.name": "soundsplitter_cable_input",
                                    "node.description": name,
                                    "node.nick": name,
                                    "application.name": name,
                                    "media.class": "Audio/Sink",
                                    "audio.position": ["FL", "FR"],
                                    "object.linger": False,
                                    "adapter.auto-port-config": {
                                        "mode": "dsp",
                                        "monitor": True,
                                        "position": "preserve",
                                    },
                                }
                            ),
                        ],
                    )
                    if not process.waitForStarted():
                        raise RuntimeError(process.errorString())
                    timeout.start(10_000)
                    if (
                        not any(
                            device.description() == name
                            for device in devices.audioOutputs()
                        )
                        and process.state() == QProcess.ProcessState.Running
                    ):
                        loop.exec()
                    timeout.stop()
                    if process.state() != QProcess.ProcessState.Running:
                        raise RuntimeError(
                            bytes(process.readAllStandardError().data()).decode(
                                errors="replace"
                            )
                        )
                    if not any(
                        device.description() == name
                        for device in devices.audioOutputs()
                    ):
                        raise RuntimeError(
                            "PipeWire audio output did not appear within 10 seconds"
                        )
                    yield
                finally:
                    timeout.stop()
                    process.kill()
                    process.waitForFinished(msecs=1000)

    def __new__(cls) -> Container:
        return make_container(cls._Provider())
