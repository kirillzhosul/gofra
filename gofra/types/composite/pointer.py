from gofra.types._base import CompositeType, Type


class PointerType(CompositeType):
    """Type that holds another type it points to."""

    points_to: Type
    size_in_bytes: int = 8  # Wide pointers as being on 64-bits machine

    def __init__(self, points_to: Type) -> None:
        self.points_to = points_to

    def __repr__(self) -> str:
        return f"*{self.points_to}"
