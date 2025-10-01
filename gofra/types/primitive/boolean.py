from gofra.types._base import PrimitiveType


class BoolType(PrimitiveType):
    """Boolean type as an almost as-is alias to an integer."""

    size_in_bytes = 8  # TODO(@kirillzhosul): Checkout usage without whole 8 bytes

    def __repr__(self) -> str:
        return "Boolean"
