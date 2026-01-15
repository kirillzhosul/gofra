from libgofra.types._base import PrimitiveType


class BoolType(PrimitiveType):
    """Boolean type as an almost as-is alias to an integer."""

    size_in_bytes = 8  # TODO(@kirillzhosul): Checkout usage without whole 8 bytes
    alignment = 8

    def __repr__(self) -> str:
        return "Bool"
