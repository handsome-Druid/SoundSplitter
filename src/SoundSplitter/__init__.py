from typing import NoReturn

from .integration import APP, DI, Logger


def main() -> NoReturn:
    APP(DI(), Logger)()
