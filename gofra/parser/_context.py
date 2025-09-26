from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .operators import Operator, OperatorOperand, OperatorType

if TYPE_CHECKING:
    from collections.abc import (
        Generator,
        MutableMapping,
        MutableSequence,
    )
    from pathlib import Path

    from gofra.lexer import Token
    from gofra.parser.functions import Function
    from gofra.parser.variables import Variable


@dataclass(frozen=False)
class ParserContext:
    """Context for parsing which only required from internal usages."""

    tokenizer: Generator[Token]
    parent: ParserContext | None

    # Resulting operators from parsing
    operators: MutableSequence[Operator] = field(default_factory=lambda: list())  # noqa: C408

    functions: MutableMapping[str, Function] = field(default_factory=lambda: dict())  # noqa: C408
    variables: OrderedDict[str, Variable] = field(
        default_factory=lambda: OrderedDict(),
    )

    context_stack: deque[tuple[int, Operator]] = field(default_factory=lambda: deque())
    included_source_paths: set[Path] = field(default_factory=lambda: set())

    current_operator: int = field(default=0)

    def has_context_stack(self) -> bool:
        return len(self.context_stack) > 0

    def add_function(self, function: Function) -> Function:
        self.functions[function.name] = function
        return function

    @property
    def is_top_level(self) -> bool:
        return self.parent is None

    def expand_from_inline_block(self, inline_block: Function) -> None:
        if inline_block.external_definition_link_to:
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
