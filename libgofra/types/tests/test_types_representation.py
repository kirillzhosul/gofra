from libgofra.types.composite.array import ArrayType
from libgofra.types.composite.pointer import PointerType
from libgofra.types.composite.string import StringType


def test_array_subtype_representation_ambiguity() -> None:
    """Array of pointers and pointer to array must distinguished and not ambiguous."""
    t1 = repr(ArrayType(PointerType(StringType()), 0))
    t2 = repr(PointerType(ArrayType(StringType(), 0)))

    assert t1 != t2
