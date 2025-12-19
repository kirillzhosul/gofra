from libgofra.types.composite.string import StringType
from libgofra.types.generics import GenericParametrizedType
from libgofra.types.primitive.boolean import BoolType
from libgofra.types.primitive.character import CharType
from libgofra.types.primitive.integers import I64Type
from libgofra.types.primitive.void import VoidType

from ._base import Type


class TypeRegistry(dict[str, Type | GenericParametrizedType]):
    def copy(self) -> "TypeRegistry":
        return TypeRegistry(super().copy())


DEFAULT_PRIMITIVE_TYPE_REGISTRY = TypeRegistry(
    {
        "int": I64Type(),
        "i64": I64Type(),
        "char": CharType(),
        "void": VoidType(),
        "bool": BoolType(),
        # It is only half primitive
        "string": StringType(),
    },
)
