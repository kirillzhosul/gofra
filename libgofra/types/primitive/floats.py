from libgofra.types._base import PrimitiveType


class F64Type(PrimitiveType):
    """Float of size 64 bits."""

    size_in_bytes = 8
    alignment = 8

    is_fp = True

    def __repr__(self) -> str:
        return "F64"


type AnyFloatType = F64Type
