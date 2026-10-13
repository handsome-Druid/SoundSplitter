from collections.abc import Generator

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

    def __new__(cls) -> Container:
        return make_container(cls._Provider())
