from collections.abc import Mapping, Sequence

from gofra.types._base import CompositeType, Type


class StructureType(CompositeType):
    """Type that holds fields with their types as structure."""

    # Direct mapping from name of the field to its direct type
    fields: Mapping[str, Type]

    # Order of name for offsetting in `fields`, as mapping does not contain any order information
    fields_ordering: Sequence[str]

    name: str
    size_in_bytes: int

    def __init__(
        self,
        name: str,
        fields: Mapping[str, Type],
        fields_ordering: Sequence[str],
        cpu_alignment_in_bytes: int,
    ) -> None:
        self.name = name
        self.fields = fields
        self.fields_ordering = fields_ordering

        self.size_in_bytes = sum(f.size_in_bytes for f in fields.values())

        # Align whole structure by alignment
        if cpu_alignment_in_bytes != 0:
            alignment = cpu_alignment_in_bytes + 1
            self.size_in_bytes = (self.size_in_bytes + alignment) & ~alignment

    def __repr__(self) -> str:
        return f"Struct {self.name}"

    def get_field_offset(self, field: str) -> int:
        """Get byte offset for given field (to access this field)."""
        offset_shift = 0
        for _field in self.fields_ordering:
            if _field == field:
                break
            offset_shift += self.fields[_field].size_in_bytes
        return offset_shift
