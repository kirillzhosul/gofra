from enum import Enum, auto


class LinkerProfile(Enum):
    """Profile for high-level API of Linker.

    Impacts optimizations and debug information.
    """

    # Faster linkage, debug information is not touched
    DEBUG = auto()

    # May remove debug information and apply optimizations
    PRODUCTION = auto()
