from libgofra.feature_flags import FEATURE_ALLOW_FPU
from libgofra.types._base import PrimitiveType


class F64Type(PrimitiveType):
    """Float of size 64 bits."""

    size_in_bytes = 8
    is_fp = True

    def __init__(self) -> None:
        if not FEATURE_ALLOW_FPU:
            raise ValueError

    def __repr__(self) -> str:
        return "F64"


type AnyFloatType = F64Type
