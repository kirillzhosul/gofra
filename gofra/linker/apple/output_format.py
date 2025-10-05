from enum import Enum, auto


class AppleLinkerOutputFormat(Enum):
    """Formats of output that Apple Linker may emit after linkage process."""

    # Mach-O main executable
    EXECUTABLE = auto()  # MH_EXECUTE

    # Mach-O shared library
    SHARED_LIBRARY = auto()  # MH_DYLIB

    # Merge object files into single one
    OBJECT_FILE = auto()  # MH_OBJECT

    # Notice:
    # Only formats above is used (or should be used)
    # formats below is some non-general and non-crossplatform Darwin/MacOS specific type of shit

    # Mach-O bundle
    # Note (@kirillzhosul): this is some weird type of output
    # maybe sometime we will use that but at current moment there is no need in that
    BUNDLE = auto()  # MH_BUNDLE

    # Mach-O dylinker
    # Notice: only used when building dyld
    # probably, should not be used inside our toolchain
    DYLINKER = auto()  # MH_DYLINKER


class AppleLinkerOutputFormatKindFlag(Enum):
    """Additional kind flags for `AppleLinkerOutputFormat`."""

    # Default one (implied by underling `ld` tool by `EXECUTABLE`, `BUNDLE`, `SHARED_LIBRARY`)
    DYNAMIC = auto()

    # Does not use `dyld`.
    # Notice: Only used building kernel
    # probably, should not be used inside our toolchain
    STATIC = auto()

    # Produces a mach-o file in which the mach_header, load commands, and symbol table are not in any segment
    # This output type is used for firmware or embedded development where the segments are copied out of the mach-o into ROM/Flash.
    # Notice:
    # probably, should not be used inside our toolchain
    PRELOAD = auto()
