from libgofra.types.composite.structure import StructureType
from libgofra.types.primitive.character import CharType
from libgofra.types.primitive.integers import I64Type


def test_structure_reordering() -> None:
    reordered = StructureType(
        name="test",
        fields={
            "c1": CharType(),
            "i": I64Type(),
            "c2": CharType(),
        },
        order=["c1", "i", "c2"],
        is_packed=True,
        reorder=True,
    )
    assert reordered.was_reordered
    assert reordered.order == ["i", "c1", "c2"]

    assert not StructureType(
        name="test",
        fields={
            "c1": CharType(),
            "i": I64Type(),
            "c2": CharType(),
        },
        order=["i", "c1", "c2"],
        is_packed=True,
        reorder=True,
    ).was_reordered
