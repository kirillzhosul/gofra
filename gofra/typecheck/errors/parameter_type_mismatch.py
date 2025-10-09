from gofra.exceptions import GofraError
from gofra.hir.function import Function
from gofra.lexer.tokens import TokenLocation
from gofra.types import Type


class ParameterTypeMismatchTypecheckError(GofraError):
    def __init__(
        self,
        expected_type: Type,
        actual_type: Type,
        callee: Function,
        caller: Function,
        at: TokenLocation,
    ) -> None:
        super().__init__()
        self.expected_type = expected_type
        self.actual_type = actual_type
        self.callee = callee
        self.caller = caller
        self.at = at

    def __repr__(self) -> str:
        return f"""Parameter type mismatch at {self.at}

Function '{self.callee.name}{self.callee.parameters}' defined at {self.callee.defined_at} 
parameter type is '{self.expected_type}' but got argument of type '{self.actual_type}'

Called from '{self.caller.name}' at {self.at}
Mismatch: '{self.expected_type}' != '{self.actual_type}'

Did you miss the types or missing typecast?
[parameter-type-mismatch]"""
