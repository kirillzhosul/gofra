from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from gofra.hir.function import Function
from gofra.hir.operator import Operator, OperatorType
from gofra.types._base import Type

if TYPE_CHECKING:
    from collections.abc import (
        Generator,
        MutableMapping,
        MutableSequence,
    )
    from pathlib import Path

    from gofra.hir.variable import Variable
    from gofra.lexer import Token


@dataclass(frozen=False)
class ParserContext:
    """Context for parsing which only required from internal usages."""

    _tokenizer: Generator[Token, None]
    parent: ParserContext | None

    _peeked: Token | None = None

    # Resulting operators from parsing
    operators: MutableSequence[Operator] = field(default_factory=list[Operator])

    functions: MutableMapping[str, Function] = field(
        default_factory=dict[str, Function],
    )
    variables: OrderedDict[str, Variable] = field(
        default_factory=OrderedDict[str, "Variable"],
    )

    context_stack: deque[tuple[int, Operator]] = field(default_factory=lambda: deque())
    included_source_paths: set[Path] = field(default_factory=lambda: set())

    # No function calls in that context
    # Maybe should be refactored
    is_leaf_context: bool = True

    current_operator: int = field(default=0)

    def has_context_stack(self) -> bool:
        return len(self.context_stack) > 0

    def add_function(self, function: Function) -> Function:
        self.functions[function.name] = function

        return function

    @property
    def is_top_level(self) -> bool:
        return self.parent is None

    def next_token(self) -> Token:
        if self._peeked is not None:
            token = self._peeked
            self._peeked = None
            return token
        return next(self._tokenizer)

    def peek_token(self) -> Token:
        if self._peeked is None:
            self._peeked = next(self._tokenizer)
        return self._peeked

    def expand_from_inline_block(self, inline_block: Function) -> None:
        if inline_block.is_external:
            msg = "Cannot expand extern function."
            raise ValueError(msg)
        self.current_operator += len(inline_block.operators)
        self.operators.extend(inline_block.operators)

    def pop_context_stack(self) -> tuple[int, Operator]:
        return self.context_stack.pop()

    def push_new_operator(
        self,
        type: OperatorType,  # noqa: A002
        token: Token,
        operand: int | str | Type | None = None,
        *,
        is_contextual: bool = False,
    ) -> None:
        if type == OperatorType.FUNCTION_CALL:
            self.is_leaf_context = False

        operator = Operator(
            type=type,
            token=token,
            operand=operand,
        )
        self.operators.append(operator)
        if is_contextual:
            self.context_stack.append((self.current_operator, operator))
        self.current_operator += 1
