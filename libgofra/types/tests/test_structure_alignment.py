from libgofra.types.composite.structure import StructureType
from libgofra.types.primitive.character import CharType
from libgofra.types.primitive.integers import I64Type


def test_packed_structure_alignment() -> None:
    assert (
        StructureType(
            name="test",
            fields={"i": I64Type()},
            order=["i"],
            is_packed=True,
        ).size_in_bytes
        == I64Type.size_in_bytes  # 8
    )
    assert (
        StructureType(
            name="test",
            fields={"x": CharType(), "i": I64Type()},
            order=["x", "i"],
            is_packed=True,
        ).size_in_bytes
        == CharType().size_in_bytes + I64Type.size_in_bytes  # 9, packed
    )


def test_aligned_structure_alignment() -> None:
    assert (
        StructureType(
            name="test",
            fields={"i": I64Type()},
            order=["i"],
            is_packed=False,
        ).size_in_bytes
        == I64Type.size_in_bytes  # 8
    )
    assert (
        StructureType(
            name="test",
            fields={"x": CharType(), "i": I64Type()},
            order=["x", "i"],
            is_packed=False,
        ).size_in_bytes
        == CharType().size_in_bytes
        + I64Type.size_in_bytes
        + 7  # 16, aligned, 7 bytes padding
    )
