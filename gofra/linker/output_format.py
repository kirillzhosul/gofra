from enum import Enum, auto


class LinkerOutputFormat(Enum):
    """Which type of output should base linker emit."""

    # Simple executable
    EXECUTABLE = auto()

    # Library with symbols
    LIBRARY = auto()

    # Another object file
    OBJECT = auto()
