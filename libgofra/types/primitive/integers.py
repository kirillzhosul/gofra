from libgofra.types._base import PrimitiveType


class IntegerType(PrimitiveType): ...


class I64Type(IntegerType):
    """Integer of size 64 bits."""

    size_in_bytes = 8
    alignment = size_in_bytes

    def __repr__(self) -> str:
        return "I64"


class I32Type(IntegerType):
    """Integer of size 32 bits."""

    size_in_bytes = 4
    alignment = size_in_bytes

    def __repr__(self) -> str:
        return "I32"


class I16Type(IntegerType):
    """Integer of size 16 bits."""

    size_in_bytes = 2
    alignment = size_in_bytes

    def __repr__(self) -> str:
        return "I16"


class I8Type(IntegerType):
    """Integer of size 8 bits."""

    size_in_bytes = 1
    alignment = size_in_bytes

    def __repr__(self) -> str:
        return "I8"
