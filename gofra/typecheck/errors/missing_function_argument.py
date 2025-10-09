from collections.abc import Sequence

from gofra.exceptions import GofraError
from gofra.hir.function import Function
from gofra.lexer.tokens import TokenLocation
from gofra.types import Type


class MissingFunctionArgumentsTypecheckError(GofraError):
    def __init__(
        self,
        *args: object,
        typestack: Sequence[Type],
        caller: Function,
        callee: Function,
        at: TokenLocation,
    ) -> None:
        super().__init__(*args)
        self.typestack = typestack
        self.callee = callee
        self.caller = caller
        self.at = at

    def __repr__(self) -> str:
        missing_count = len(self.callee.parameters) - len(self.typestack)
        return f"""Not enough function arguments at {self.at}

Function '{self.callee.name}{self.callee.parameters}' defined at {self.callee.defined_at} 
expects {missing_count} more arguments on stack

Mismatch (stack): {self.typestack} != {self.callee.parameters}

Called from '{self.caller.name}' at {self.at}

[missing-function-arguments]"""
