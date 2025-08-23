from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from gofra.parser.functions import Function

from .operators import Operator, OperatorOperand, OperatorType

if TYPE_CHECKING:
    from collections.abc import (
        Generator,
        MutableMapping,
        MutableSequence,
        Sequence,
    )
    from pathlib import Path

    from gofra.lexer import Token
    from gofra.typecheck.types import GofraType


@dataclass(frozen=False)
class ParserContext:
    """Context for parsing which only required from internal usages."""

    tokenizer: Generator[Token]

    # Should be refactored
    is_top_level: bool

    # Resulting operators from parsing
    operators: MutableSequence[Operator] = field(default_factory=lambda: list())  # noqa: C408

    functions: MutableMapping[str, Function] = field(default_factory=lambda: dict())  # noqa: C408
    memories: MutableMapping[str, int] = field(default_factory=lambda: dict())  # noqa: C408

    context_stack: deque[tuple[int, Operator]] = field(default_factory=lambda: deque())
    included_source_paths: set[Path] = field(default_factory=lambda: set())

    current_operator: int = field(default=0)

    def has_context_stack(self) -> bool:
        return len(self.context_stack) > 0

    def new_function(
        self,
        from_token: Token,
        name: str,
        *,
        type_contract_in: Sequence[GofraType],
        type_contract_out: Sequence[GofraType],
        emit_inline_body: bool,
        is_externally_defined: bool,
        is_global_linker_symbol: bool,
        source: Sequence[Operator],
    ) -> Function:
        function = Function(
            location=from_token.location,
            name=name,
            source=source,
            type_contract_in=type_contract_in,
            type_contract_out=type_contract_out,
            emit_inline_body=emit_inline_body,
            is_externally_defined=is_externally_defined,
            is_global_linker_symbol=is_global_linker_symbol,
        )
        self.functions[name] = function
        return function

    def expand_from_inline_block(self, inline_block: Function) -> None:
        if inline_block.is_externally_defined:
            msg = "Cannot expand extern function."
            raise ValueError(msg)
        self.current_operator += len(inline_block.source)
        self.operators.extend(inline_block.source)

    def pop_context_stack(self) -> tuple[int, Operator]:
        return self.context_stack.pop()

    def push_new_operator(
        self,
        type: OperatorType,  # noqa: A002
        token: Token,
        operand: OperatorOperand,
        *,
        is_contextual: bool,
    ) -> None:
        operator = Operator(
            type=type,
            token=token,
            operand=operand,
            has_optimizations=False,
        )
        self.operators.append(operator)
        if is_contextual:
            self.context_stack.append((self.current_operator, operator))
        self.current_operator += 1
