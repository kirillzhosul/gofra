from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from gofra.parser.functions import Function

from .macros import Macro
from .operators import Operator, OperatorOperand, OperatorType

if TYPE_CHECKING:
    from collections.abc import Iterable, MutableMapping, MutableSequence, Sequence
    from pathlib import Path

    from gofra.lexer import Token
    from gofra.typecheck.types import GofraType


@dataclass(frozen=False)
class ParserContext:
    """Context for parsing which only required from internal usages."""

    parsing_from_path: Path
    include_search_directories: Iterable[Path]

    tokens: deque[Token]

    # Should be refactored
    is_top_level: bool

    # Resulting operators from parsing
    operators: MutableSequence[Operator] = field(default_factory=lambda: list())  # noqa: C408

    macros: MutableMapping[str, Macro] = field(default_factory=lambda: dict())  # noqa: C408
    functions: MutableMapping[str, Function] = field(default_factory=lambda: dict())  # noqa: C408
    memories: MutableMapping[str, int] = field(default_factory=lambda: dict())  # noqa: C408

    context_stack: deque[tuple[int, Operator]] = field(default_factory=lambda: deque())
    included_source_paths: set[Path] = field(default_factory=lambda: set())

    current_operator: int = field(default=0)
    current_token_index: int = 0

    def __post_init__(self) -> None:
        assert self.tokens
        self.included_source_paths.add(self.parsing_from_path)

    def tokens_exhausted(self) -> bool:
        return self.current_token_index >= len(self.tokens)

    def has_context_stack(self) -> bool:
        return len(self.context_stack) > 0

    def new_macro(self, from_token: Token, name: str) -> Macro:
        macro = Macro(location=from_token.location, inner_tokens=[], name=name)
        self.macros[name] = macro
        return macro

    def next_token(self) -> Token:
        token = self.tokens[self.current_token_index]
        self.current_token_index += 1
        return token

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

    def expand_from_inline_block(self, inline_block: Macro | Function) -> None:
        if isinstance(inline_block, Function):
            if inline_block.is_externally_defined:
                msg = "Cannot expand extern function."
                raise ValueError(msg)
            self.current_operator += len(inline_block.source)
            self.operators.extend(inline_block.source)
            return

        for token in inline_block.inner_tokens:
            self.tokens.insert(self.current_token_index, token)

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
