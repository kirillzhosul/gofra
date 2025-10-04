from collections.abc import Sequence

from gofra.exceptions import GofraError
from gofra.lexer.tokens import TokenLocation
from gofra.parser.functions.function import Function
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
        missing_count = len(self.callee.type_contract_in) - len(self.typestack)
        return f"""Not enough function arguments at {self.at}

Function '{self.callee.name}{self.callee.type_contract_in}' defined at {self.callee.location} 
expects {missing_count} more arguments on stack

Mismatch (stack): {self.typestack} != {self.callee.type_contract_in}

Called from '{self.caller.name}' at {self.at}

[missing-function-arguments]"""
