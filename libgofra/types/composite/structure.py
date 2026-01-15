from collections.abc import Mapping, MutableMapping, Sequence

from libgofra.types._base import CompositeType, Type


class StructureType(CompositeType):
    """Type that holds fields with their types as structure."""

    _natural_fields: Mapping[str, Type]
    _natural_order: Sequence[str]

    _field_offsets: MutableMapping[str, int]
    _is_packed: bool

    name: str
    size_in_bytes: int

    def __init__(
        self,
        name: str,
        fields: Mapping[str, Type],
        order: Sequence[str],
        *,
        is_packed: bool,
    ) -> None:
        self.name = name
        self._natural_fields = fields
        self._natural_order = order
        self._field_offsets = {}
        self._is_packed = is_packed
        self._rebuild()

    def __repr__(self) -> str:
        status = "packed" if self.is_packed else "aligned"
        return f"Struct {self.name} ({status})"

    def _rebuild(self) -> None:
        assert list(self.natural_fields.keys()) == list(self.natural_order)
        self._field_offsets = {}
        if self.is_packed:
            return self._rebuild_packed()
        return self._rebuild_unpacked()

    def _rebuild_unpacked(self) -> None:
        assert not self.is_packed

        offset = 0
        alignment = 1
        for field in self.natural_order:
            field_type = self.get_field_type(field)
            field_alignment = field_type.alignment
            alignment = max(alignment, field_alignment)

            if offset % field_alignment != 0:
                padding = field_alignment - (offset % field_alignment)
                offset += padding

            self._field_offsets[field] = offset
            offset += field_type.size_in_bytes

        if offset % alignment != 0:
            # Ending padding
            padding = alignment - (offset % alignment)
            offset += padding

        self.size_in_bytes = offset

    def _rebuild_packed(self) -> None:
        assert self.is_packed

        offset = 0
        for field in self._natural_order:
            assert self.has_field(field)
            self._field_offsets[field] = offset

            field_size = self.get_field_type(field).size_in_bytes
            offset += field_size

        self.size_in_bytes = offset

    def get_field_offset(self, field_name: str) -> int:
        """Get byte offset for given field (to access this field). Applies alignment if packed."""
        assert self.has_field(field_name)
        return self._field_offsets[field_name]

    def get_field_type(self, field_name: str) -> Type:
        """Get underlying type of field by name."""
        assert field_name in self._natural_fields
        return self._natural_fields[field_name]

    def backpatch(self, fields: Mapping[str, Type], order: Sequence[str]) -> None:
        """Backpatch structure with new fields.

        Required when building an structure as *reference* (e.g non-immediate structure parsing)
        """
        self._natural_fields = fields
        self._natural_order = order
        self._rebuild()

    def has_field(self, field_name: str) -> bool:
        """Is structure has this field in natural fields?."""
        return field_name in self._natural_fields

    @property
    def natural_fields(self) -> Mapping[str, Type]:
        """Mapping from field name to its corresponding type as specified within structure content.

        Does not apply any alignment, order as-is.
        """
        return self._natural_fields

    @property
    def natural_order(self) -> Sequence[str]:
        """Order of fields in structure as specified within structure content."""
        return self._natural_order

    @property
    def is_packed(self) -> bool:
        """Is structure applies reordering/alignment."""
        return self._is_packed
