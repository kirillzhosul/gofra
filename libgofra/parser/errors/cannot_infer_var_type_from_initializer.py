from libgofra.exceptions import GofraError
from libgofra.lexer.tokens import TokenLocation


class CannotInferVariableTypeFromInitializerError(GofraError):
    def __init__(self, varname: str, at: TokenLocation) -> None:
        self.varname = varname
        self.at = at

    def __repr__(self) -> str:
        return f"""Unable to infer variable type from initializer!

Variable '{self.varname}' defined at {self.at} has no type (auto type var) and unable to infer its type from specified initializer
Consider adding type explicitly.

{self.generic_error_name}"""
