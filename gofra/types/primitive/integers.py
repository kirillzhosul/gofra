from gofra.types._base import PrimitiveType


class I64Type(PrimitiveType):
    """Integer of size 64 bits."""

    size_in_bytes = 8

    def __repr__(self) -> str:
        return "I64"
