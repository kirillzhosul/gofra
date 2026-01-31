from libgofra.types.composite.array import ArrayType
from libgofra.types.composite.pointer import PointerMemoryLocation, PointerType
from libgofra.types.composite.structure import StructureType
from libgofra.types.primitive.character import CharType
from libgofra.types.primitive.integers import I64Type


class StringType(StructureType):
    """Type that holds string as an slice of CString."""

    def __init__(self) -> None:
        super().__init__(
            name="String",
            fields={
                "data": PointerType(
                    ArrayType(
                        element_type=CharType(),
                        elements_count=0,
                    ),
                    memory_location=PointerMemoryLocation.STATIC_READONLY,
                ),
                "len": I64Type(),
            },
            order=["data", "len"],
            is_packed=True,
            reorder=False,
        )

    def __repr__(self) -> str:
        return self.name
