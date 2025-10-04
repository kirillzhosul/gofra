from gofra.types import Type
from gofra.types.composite.array import ArrayType
from gofra.types.composite.pointer import PointerType
from gofra.types.primitive.boolean import BoolType
from gofra.types.primitive.character import CharType
from gofra.types.primitive.integers import I64Type
from gofra.types.primitive.void import VoidType
from gofra.types.registry import PRIMITIVE_TYPE_REGISTRY

_PRIMITIVE_TYPES_CLS: dict[str, type[Type]] = {
    "int": I64Type,
    "void": VoidType,
    "bool": BoolType,
    "char": CharType,
}


def parse_type(typename: str) -> Type | None:
    if primitive_registry_type := PRIMITIVE_TYPE_REGISTRY.get(typename, None):
        return primitive_registry_type

    if typename.startswith("*"):
        poins_to = parse_type(typename.removeprefix("*"))
        if not poins_to:
            return None
        return PointerType(poins_to)

    if "[" in typename:
        array_type = parse_type(typename.split("[")[0])
        if not array_type:
            return None
        array_size = typename.split("[", maxsplit=1)[1].removesuffix("]")

        if array_size == "" or array_size.isdigit():
            array_elements = int(array_size or "0")
            return ArrayType(element_type=array_type, elements_count=array_elements)

    return None
