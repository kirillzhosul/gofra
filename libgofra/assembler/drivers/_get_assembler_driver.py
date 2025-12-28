from collections.abc import Iterable

from libgofra.targets.target import Target

from ._driver_protocol import AssemblerDriverProtocol
from .clang import ClangAssemblerDriver

_drivers = [ClangAssemblerDriver]


def get_assembler_driver(target: Target) -> AssemblerDriverProtocol | None:
    """Get supported assembler (driver) for that target.

    Returns None if no suitable assembler either installed or supports that target
    """
    for driver in _drivers:
        if not driver.is_installed():
            return None
        if not driver.is_supported(target):
            return None
        return driver()
    return None


def get_all_drivers() -> Iterable[type[AssemblerDriverProtocol]]:
    """Acquire list of all drivers that is used."""
    return _drivers
