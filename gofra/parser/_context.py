from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from gofra.hir.function import Function
from gofra.hir.operator import Operator, OperatorType
from gofra.parser.errors.general_expect_token import ExpectedTokenByParserError
from gofra.types.composite.structure import StructureType

if TYPE_CHECKING:
    from collections.abc import (
        Generator,
        MutableMapping,
        MutableSequence,
    )

    from gofra.hir.variable import Variable
    from gofra.lexer import Token
    from gofra.lexer.tokens import TokenType
    from gofra.types._base import Type


@dataclass
class PeekableTokenizer:
    _tokenizer: Generator[Token] = field()
    _peeked: Token | None = field(default=None)

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

    def expect_token(self, type: TokenType) -> None:  # noqa: A002
        token = self.peek_token()
        if token.type != type:
            raise ExpectedTokenByParserError(expected=type, got=token)


@dataclass(frozen=False)
class ParserContext(PeekableTokenizer):
    """Context for parsing which only required from internal usages."""

    parent: ParserContext | None = field(default=None)

    # Resulting operators from parsing
    operators: MutableSequence[Operator] = field(default_factory=list[Operator])

    context_stack: deque[tuple[int, Operator, tuple[Variable, int] | None]] = field(
        default_factory=lambda: deque(),
    )
    variables: MutableMapping[str, Variable] = field(
        default_factory=dict[str, "Variable"],
    )

    structs: MutableMapping[str, StructureType] = field(
        default_factory=dict[str, StructureType],
    )
    functions: MutableMapping[str, Function] = field(
        default_factory=dict[str, Function],
    )

    # No function calls in that context
    # Maybe should be refactored
    is_leaf_context: bool = True

    def name_is_already_taken(self, name: str) -> bool:
        is_taken = any(
            name in container
            for container in (self.structs, self.variables, self.functions)
        )

        if not is_taken and self.parent:
            return self.parent.name_is_already_taken(name)
        return is_taken

    def has_context_stack(self) -> bool:
        return len(self.context_stack) > 0

    def get_struct(self, name: str) -> StructureType | None:
        if name in self.structs:
            return self.structs[name]
        if self.parent:
            return self.parent.get_struct(name)
        return None

    def add_function(self, function: Function) -> Function:
        self.functions[function.name] = function

        return function

    def search_variable_in_context_parents(
        self,
        variable: str,
    ) -> Variable | None:
        context_ref = self

        while True:
            if variable in context_ref.variables:
                return context_ref.variables[variable]

            if context_ref.parent:
                context_ref = context_ref.parent
                continue

            return None

    @property
    def is_top_level(self) -> bool:
        return self.parent is None

    @property
    def current_operator(self) -> int:
        return len(self.operators)

    def expand_from_inline_block(self, inline_block: Function) -> None:
        if inline_block.is_external:
            msg = "Cannot expand extern function."
            raise ValueError(msg)
        self.operators.extend(inline_block.operators)

    def pop_context_stack(self) -> tuple[int, Operator, tuple[Variable, int] | None]:
        return self.context_stack.pop()

    def push_new_operator(
        self,
        type: OperatorType,  # noqa: A002
        token: Token,
        operand: float | str | Type | None = None,
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
            self.context_stack.append((self.current_operator - 1, operator, None))
