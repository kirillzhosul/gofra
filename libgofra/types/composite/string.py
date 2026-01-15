from collections.abc import Mapping, Sequence

from libgofra.types._base import Type
from libgofra.types.composite.array import ArrayType
from libgofra.types.composite.pointer import PointerType
from libgofra.types.composite.structure import StructureType
from libgofra.types.primitive.character import CharType
from libgofra.types.primitive.integers import I64Type


class StringType(StructureType):
    """Type that holds string as an slice of CString."""

    # Direct mapping from name of the field to its direct type
    _natural_fields: Mapping[str, Type] = {
        "data": PointerType(
            ArrayType(
                element_type=CharType(),
                elements_count=0,
            ),
        ),
        "len": I64Type(),
    }

    # Order of name for offsetting in `fields`, as mapping does not contain any order information
    _natural_order: Sequence[str] = ["data", "len"]

    _is_packed = False
    name: str = "String"

    def __init__(self) -> None:
        self._rebuild()

    def __repr__(self) -> str:
        return self.name
