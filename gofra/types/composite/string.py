from collections.abc import Mapping, Sequence

from gofra.types._base import Type
from gofra.types.composite.array import ArrayType
from gofra.types.composite.pointer import PointerType
from gofra.types.composite.structure import StructureType
from gofra.types.primitive.character import CharType
from gofra.types.primitive.integers import I64Type


class StringType(StructureType):
    """Type that holds string as an slice of CString."""

    # Direct mapping from name of the field to its direct type
    fields: Mapping[str, Type] = {
        "data": PointerType(
            ArrayType(
                element_type=CharType(),
                elements_count=0,
            ),
        ),
        "len": I64Type(),
    }

    # Order of name for offsetting in `fields`, as mapping does not contain any order information
    fields_ordering: Sequence[str] = ["data", "len"]

    name: str = "String"
    size_in_bytes: int

    cpu_alignment_in_bytes: int = 8

    def __init__(self) -> None:
        self.recalculate_size_in_bytes()

    def recalculate_size_in_bytes(self) -> None:
        self.size_in_bytes = sum(f.size_in_bytes for f in self.fields.values())

        # Align whole structure by alignment
        if self.cpu_alignment_in_bytes != 0:
            alignment = self.cpu_alignment_in_bytes + 1
            self.size_in_bytes = (self.size_in_bytes + alignment) & ~alignment

    def __repr__(self) -> str:
        return self.name

    def get_field_offset(self, field: str) -> int:
        """Get byte offset for given field (to access this field)."""
        offset_shift = 0
        for _field in self.fields_ordering:
            if _field == field:
                break
            offset_shift += self.fields[_field].size_in_bytes
        return offset_shift
