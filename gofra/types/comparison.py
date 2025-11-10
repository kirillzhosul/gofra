from typing import Literal, assert_never

from gofra.types.composite.array import ArrayType
from gofra.types.composite.pointer import PointerType
from gofra.types.composite.structure import StructureType

from ._base import PrimitiveType, Type


def is_primitive_type(a: Type) -> bool:
    return isinstance(a, PrimitiveType)


def is_types_same(
    a: Type,
    b: Type,
    *,
    strategy: Literal["strict-same-type", "implicit-byte-size"] = "strict-same-type",
) -> bool:
    match strategy:
        case "strict-same-type":
            return _compare_types_strict_same_type(a, b)
        case "implicit-byte-size":
            # TODO(@kirillzhosul): Probably required proper check even for that simple strategy, as I64 is same as *void, but should be generous
            return a.size_in_bytes == b.size_in_bytes
        case _:
            assert_never(strategy)


def _compare_types_strict_same_type(a: Type, b: Type) -> bool:
    if is_primitive_type(a) and is_primitive_type(b):
        # primitives types without narrowing is just check of equality
        return type(a) is type(b)

    # when one type is an primitive it is never comparable to other, complex type
    # e.g pointer and integer is never comparable beside explicit typecast

    if is_primitive_type(a):
        # a -> primitive
        # b -> complex
        return False

    if is_primitive_type(b):
        # a -> complex
        # b -> primitive
        return False

    # Both are complex types

    if isinstance(a, StructureType) and isinstance(b, StructureType):
        return a.name == b.name and a.fields_ordering == b.fields_ordering

    if isinstance(a, PointerType) and isinstance(b, PointerType):
        return is_types_same(
            _try_unwrap_array_element_type(a.points_to),
            _try_unwrap_array_element_type(b.points_to),
        )

    if isinstance(a, ArrayType) and isinstance(b, ArrayType):
        return (
            a.elements_count == b.elements_count
            or (a.elements_count == 0 or b.elements_count == 0)
        ) and is_types_same(
            a.element_type,
            b.element_type,
        )

    return False


def _try_unwrap_array_element_type(x: Type) -> Type:
    if isinstance(x, ArrayType):
        return x.element_type
    return x
