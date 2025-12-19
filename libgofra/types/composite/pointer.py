from enum import Enum, auto

from libgofra.types._base import CompositeType, Type


class PointerMemoryLocation(Enum):
    STACK = auto()
    HEAP = auto()
    STATIC = auto()


class PointerType(CompositeType):
    """Type that holds another type it points to."""

    points_to: Type
    size_in_bytes: int = 8  # Wide pointers as being on 64-bits machine

    memory_location: PointerMemoryLocation | None = None

    def __init__(
        self,
        points_to: Type,
        memory_location: PointerMemoryLocation | None = None,
    ) -> None:
        self.points_to = points_to
        self.memory_location = memory_location

    def __repr__(self) -> str:
        return f"*{self.points_to}"
