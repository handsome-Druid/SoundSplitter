from collections.abc import Generator
from subprocess import run
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
            result = run(
                [
                    "pactl",
                    "load-module",
                    "module-null-sink",
                    "sink_name=soundsplitter_cable_input",
                    "channels=2",
                    "channel_map=front-left,front-right",
                    'sink_properties=device.description="CABLE Input (SoundSplitter)"',
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            try:
                yield
            finally:
                run(
                    ["pactl", "unload-module", result.stdout.strip()],
                    check=True,
                    capture_output=True,
                    text=True,
                )

    def __new__(cls) -> Container:
        return make_container(cls._Provider())
