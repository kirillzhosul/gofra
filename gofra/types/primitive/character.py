from gofra.types._base import PrimitiveType


class CharType(PrimitiveType):
    """Character type as an almost as-is alias to an integer."""

    size_in_bytes = 1

    def __repr__(self) -> str:
        return "Character"
