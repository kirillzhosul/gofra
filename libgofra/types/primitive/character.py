from libgofra.types._base import PrimitiveType


class CharType(PrimitiveType):
    """Character type as an almost as-is alias to an integer."""

    size_in_bytes = 1
    alignment = size_in_bytes

    def __repr__(self) -> str:
        return "char"
