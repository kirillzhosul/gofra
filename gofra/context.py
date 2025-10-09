from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from gofra.hir.function import Function
    from gofra.hir.variable import Variable
    from gofra.parser._context import ParserContext


@dataclass(frozen=False)
class ProgramContext:
    """Context for program which only required for internal usages.

    Acquired from parser context and mutable within next stages.
    """

    functions: MutableMapping[str, Function]
    global_variables: MutableMapping[str, Variable]
    entry_point: Function

    @staticmethod
    def from_parser_context(
        parser_context: ParserContext,
        entry_point: Function,
    ) -> ProgramContext:
        return ProgramContext(
            functions=parser_context.functions,
            global_variables=parser_context.variables,
            entry_point=entry_point,
        )
