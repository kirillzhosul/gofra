from gofra.types.composite.string import StringType
from gofra.types.generics import GenericParametrizedType
from gofra.types.primitive.boolean import BoolType
from gofra.types.primitive.character import CharType
from gofra.types.primitive.integers import I64Type
from gofra.types.primitive.void import VoidType

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
