from collections.abc import Generator
from json import dumps
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

        @provide(scope=AshkaScope.BOOTSTRAP)
        @staticmethod
        def _cable() -> Generator[None]:
            if platform != "linux":
                yield
                return
            process = QProcess()
            devices = QMediaDevices()
            loop = QEventLoop()
            timeout = QTimer()
            timeout.setSingleShot(True)
            ready = False
            failure: str | None = None
            input_name = "CABLE Output (SoundSplitter)"
            output_name = "CABLE Input (SoundSplitter)"

            def check(*_: object) -> None:
                nonlocal ready, failure
                if process.state() == QProcess.ProcessState.NotRunning:
                    failure = (
                        process.readAllStandardError().data()
                        .decode(errors="replace")
                        .strip()
                        or process.errorString()
                    )
                    loop.quit()
                    return
                ready = process.state() == QProcess.ProcessState.Running and (
                    any(
                        device.description() == input_name
                        for device in devices.audioInputs()
                    )
                    and any(
                        device.description() == output_name
                        for device in devices.audioOutputs()
                    )
                )
                if ready:
                    loop.quit()

            def on_timeout() -> None:
                nonlocal failure
                failure = (
                    "PipeWire virtual audio endpoints did not appear within 10 seconds"
                )
                loop.quit()

            process.setProgram("pw-loopback")
            process.setArguments(
                [
                    "--channels=2",
                    "--channel-map=FL,FR",
                    "--capture-props="
                    + dumps(
                        {
                            "media.class": "Audio/Sink",
                            "node.name": "soundsplitter_cable_input",
                            "node.description": output_name,
                            "node.virtual": True,
                            "node.autoconnect": False,
                            "audio.position": ["FL", "FR"],
                        }
                    ),
                    "--playback-props="
                    + dumps(
                        {
                            "media.class": "Audio/Source",
                            "node.name": "soundsplitter_cable_output",
                            "node.description": input_name,
                            "node.virtual": True,
                            "node.autoconnect": False,
                            "audio.position": ["FL", "FR"],
                        }
                    ),
                ]
            )
            devices.audioInputsChanged.connect(check)
            devices.audioOutputsChanged.connect(check)
            process.started.connect(check)
            process.finished.connect(check)
            process.errorOccurred.connect(check)
            timeout.timeout.connect(on_timeout)
            try:
                timeout.start(10_000)
                process.start()
                check()
                if not ready and failure is None:
                    loop.exec()
                timeout.stop()
                if failure is not None:
                    raise RuntimeError(
                        f"Failed to create PipeWire virtual audio cable: {failure}"
                    )
                if not ready:
                    raise RuntimeError("Waiting for PipeWire virtual audio endpoints was interrupted")
                yield
            finally:
                timeout.stop()
                devices.audioInputsChanged.disconnect(check)
                devices.audioOutputsChanged.disconnect(check)
                process.started.disconnect(check)
                process.finished.disconnect(check)
                process.errorOccurred.disconnect(check)
                timeout.timeout.disconnect(on_timeout)
                if process.state() != QProcess.ProcessState.NotRunning:
                    process.terminate()
                    if not process.waitForFinished(1000):
                        process.kill()
                        process.waitForFinished(1000)

    def __new__(cls) -> Container:
        return make_container(cls._Provider())
