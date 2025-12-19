from libgofra.exceptions import GofraError
from libgofra.lexer.tokens import TokenLocation


class ConstantVariableRequiresInitializerError(GofraError):
    def __init__(self, varname: str, at: TokenLocation) -> None:
        self.varname = varname
        self.at = at

    def __repr__(self) -> str:
        return f"""Constant variable (definition) requires initial value (initializer)!

Variable '{self.varname}' defined at {self.at} has no initial value / initializer
Consider using direct variable (non-constant).

Constants without initial value hame almost zero semantic sense.

{self.generic_error_name}"""
