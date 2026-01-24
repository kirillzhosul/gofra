from libgofra.exceptions import GofraError
from libgofra.hir.function import Function
from libgofra.lexer.tokens import TokenLocation
from libgofra.types import Type
from libgofra.types.composite.function import FunctionType


class ParameterTypeMismatchTypecheckError(GofraError):
    def __init__(
        self,
        expected_type: Type,
        actual_type: Type,
        callee: Function | FunctionType,
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

Function '{self.callee.name if isinstance(self.callee, Function) else "(anonymous)"}{self.callee.parameters}' defined at {self.callee.defined_at if isinstance(self.callee, Function) else "(anonymous)"} 
parameter type is '{self.expected_type}' but got argument of type '{self.actual_type}'

Called from '{self.caller.name}' at {self.at}
Mismatch: '{self.expected_type}' != '{self.actual_type}'

Did you miss the types or missing typecast?
[parameter-type-mismatch]"""
