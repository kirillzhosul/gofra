from collections.abc import Mapping, Sequence

from libgofra.types._base import Type


def reorder_type_fields(
    unordered: Sequence[str] | None,
    fields: Mapping[str, Type],
) -> tuple[Sequence[str], bool]:
    """Apply reordering of type fields according to their type alignment and size.

    :param unordered: Current order of fields, may be omitted to take all from fields
    :param fields: Corresponding types of fields (e.g struct)
    """

    def key(field: str) -> tuple[int, int]:
        t = fields[field]
        return (t.alignment, t.size_in_bytes)

    if unordered is None:
        unordered = list(fields.keys())

    assert set(fields.keys()) == set(unordered), "Missing fields"

    reordered = sorted(unordered, key=key, reverse=True)
    has_changed = reordered != unordered
    return reordered, has_changed
