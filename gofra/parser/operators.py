from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import TYPE_CHECKING

from gofra.types import Type

from .intrinsics import Intrinsic

if TYPE_CHECKING:
    from gofra.lexer import Token

type OperatorOperand = int | str | None | Intrinsic | Type | tuple[str, Type]


class OperatorType(IntEnum):
    PUSH_INTEGER = auto()
    PUSH_STRING = auto()
    PUSH_MEMORY_POINTER = auto()

    INTRINSIC = auto()

    IF = auto()
    WHILE = auto()
    DO = auto()
    END = auto()

    FUNCTION_RETURN = auto()
    FUNCTION_CALL = auto()
    VARIABLE_DEFINE = auto()
    TYPECAST = auto()  # Typechecker only for now


@dataclass(frozen=False)
class Operator:
    type: OperatorType
    token: Token
    operand: OperatorOperand

    jumps_to_operator_idx: int | None = field(default=None)

    syscall_optimization_omit_result: bool = field(default=False)
    syscall_optimization_injected_args: list[int | None] | None = None

    has_optimizations: bool = field(default=False)
    infer_type_after_optimization: None = field(default=None)

    def __repr__(self) -> str:
        return f"OP<{self.type.name}>"

    def is_syscall(self) -> bool:
        return self.type == OperatorType.INTRINSIC and self.operand in (
            Intrinsic.SYSCALL0,
            Intrinsic.SYSCALL1,
            Intrinsic.SYSCALL2,
            Intrinsic.SYSCALL3,
            Intrinsic.SYSCALL4,
            Intrinsic.SYSCALL5,
            Intrinsic.SYSCALL6,
        )

    def get_syscall_arguments_count(self) -> int:
        assert self.is_syscall()
        assert isinstance(self.operand, Intrinsic)
        return int(self.operand.name[-1]) + 1
