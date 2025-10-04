from gofra.types.primitive.boolean import BoolType
from gofra.types.primitive.character import CharType
from gofra.types.primitive.integers import I64Type
from gofra.types.primitive.void import VoidType

from ._base import PrimitiveType


class PrimitiveTypeRegistry:
    registry: dict[str, PrimitiveType]

    def add(self, key: str, t: PrimitiveType) -> None:
        self.registry[key] = t


PRIMITIVE_TYPE_REGISTRY = {
    "int": I64Type(),
    "i64": I64Type(),
    "char": CharType(),
    "void": VoidType(),
    "bool": BoolType(),
}
