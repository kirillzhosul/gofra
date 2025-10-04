from collections.abc import Sequence

from gofra.types._base import CompositeType, Type


class StructureType(CompositeType):
    """Type that holds fields with their types as structure."""

    fields: Sequence[Type]

    size_in_bytes: int

    def __init__(
        self,
        fields: Sequence[Type],
        cpu_alignment_in_bytes: int,
    ) -> None:
        assert cpu_alignment_in_bytes == 0, "CPU alignment is not implemented"
        self.fields = fields
        self.size_in_bytes = sum(f.size_in_bytes for f in fields)

    def __repr__(self) -> str:
        return f"Struct ({', '.join(map(repr, self.fields))})"
