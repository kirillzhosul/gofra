from libgofra.types.composite.string import StringType
from libgofra.types.generics import GenericParametrizedType
from libgofra.types.primitive.boolean import BoolType
from libgofra.types.primitive.character import CharType
from libgofra.types.primitive.floats import F64Type
from libgofra.types.primitive.integers import I8Type, I16Type, I32Type, I64Type
from libgofra.types.primitive.void import VoidType

from ._base import Type


class TypeRegistry(dict[str, Type | GenericParametrizedType]):
    def copy(self) -> "TypeRegistry":
        return TypeRegistry(super().copy())


def get_default_propagated_type_registry() -> TypeRegistry:
    return TypeRegistry(
        {
            # Int
            "int": I64Type(),
            "i64": I64Type(),
            "i32": I32Type(),
            "i16": I16Type(),
            "i8": I8Type(),
            # Etc
            "char": CharType(),
            "void": VoidType(),
            "bool": BoolType(),
            # Float
            "float": F64Type(),
            "f64": F64Type(),
            # It is only half primitive
            "string": StringType(),
        },
    )
