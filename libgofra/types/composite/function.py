from collections.abc import Sequence
from typing import TYPE_CHECKING

from libgofra.types._base import CompositeType, Type
from libgofra.types.composite.pointer import PointerType

if TYPE_CHECKING:
    from libgofra.hir.function import Function


class FunctionType(CompositeType):
    """Type that holds [pointer] to an function (e.g function itself as an type)."""

    # TODO: This may be reworked into FunctionType + FunctionPointer type
    parameters: Sequence[Type]
    return_type: Type

    size_in_bytes: int = PointerType.size_in_bytes
    alignment: int = PointerType.size_in_bytes

    def __init__(self, parameter_types: Sequence[Type], return_type: Type) -> None:
        self.parameters = parameter_types
        self.return_type = return_type

    def __repr__(self) -> str:
        return f"({', '.join(map(repr, self.parameters))}) -> {self.return_type}"

    @classmethod
    def from_hir(cls, f: "Function") -> "FunctionType":
        return FunctionType(
            parameter_types=f.parameter_types,
            return_type=f.return_type,
        )
