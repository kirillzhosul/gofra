from gofra.exceptions import GofraError
from gofra.lexer.tokens import Token
from gofra.types.primitive.void import VoidType


class VariableCannotHasVoidTypeParserError(GofraError):
    def __init__(self, varname: str, defined_at: Token) -> None:
        self.varname = varname
        self.defined_at = defined_at

    def __repr__(self) -> str:
        return f"""Void type is prohibited for variable types!

Variable '{self.varname}' defined at {self.defined_at.location} has '{VoidType()}' type, which is prohibited!
Using this type makes size of variables zero, which means it cannot have any value/invariant and has no meaning!

[parser-variable-has-void-type]"""
