from abc import ABC
from collections.abc import Mapping, MutableSequence, Sequence
from dataclasses import dataclass, field

from gofra.hir.function import Function
from gofra.lexer.tokens import TokenLocation
from gofra.types._base import Type

from .ops import LIRBaseOp


@dataclass
class LIRParameter:
    type: Type

    def __repr__(self) -> str:
        return f"Param {self.type}"


@dataclass
class LIRFunction(ABC):
    name: str
    return_type: Type
    parameters: Sequence[LIRParameter]


@dataclass
class LIRInternalFunction(LIRFunction):
    is_global_linker_symbol: bool
    hir_function_as_metadata: Function | None
    locals: Mapping[str, Type] = field(default_factory=lambda: dict())  # noqa: C408
    operations: MutableSequence[LIRBaseOp] = field(default_factory=lambda: list())  # noqa: C408

    source_location_end: TokenLocation | None = field(default=None)

    def update_location(self, location: TokenLocation) -> None:
        self.source_location_end = location

    def add_op(self, op: LIRBaseOp) -> None:
        op.source_location = self.source_location_end
        self.operations.append(op)

    def add_ops(self, *ops: LIRBaseOp) -> None:
        self.operations.extend(ops)

    @property
    def has_to_save_full_frame(self) -> bool:
        if self.hir_function_as_metadata is None:
            return True
        return (
            self.hir_function_as_metadata.is_leaf
            and not self.hir_function_as_metadata.has_local_variables
        )


@dataclass
class LIRExternFunction(LIRFunction):
    name: str
    real_name: str
    return_type: Type
    parameters: Sequence[LIRParameter]
