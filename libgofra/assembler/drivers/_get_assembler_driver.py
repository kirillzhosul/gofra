from collections.abc import Iterable

from libgofra.assembler.drivers.wabt import WabtAssemblerDriver
from libgofra.targets.target import Target

from ._driver_protocol import AssemblerDriverProtocol
from .clang import ClangAssemblerDriver

_drivers = [ClangAssemblerDriver, WabtAssemblerDriver]


def get_assembler_driver(target: Target) -> AssemblerDriverProtocol | None:
    """Get supported assembler (driver) for that target.

    Returns None if no suitable assembler either installed or supports that target
    """
    for driver in get_supported_drivers(target):
        if not driver.is_installed():
            continue
        return driver()
    return None


def get_supported_drivers(target: Target) -> list[type[AssemblerDriverProtocol]]:
    supported: list[type[AssemblerDriverProtocol]] = []
    for driver in _drivers:
        if not driver.is_supported(target):
            continue
        supported.append(driver)
    return supported


def get_all_drivers() -> Iterable[type[AssemblerDriverProtocol]]:
    """Acquire list of all drivers that is used."""
    return _drivers
