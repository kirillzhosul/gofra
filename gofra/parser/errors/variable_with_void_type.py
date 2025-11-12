from gofra.exceptions import GofraError
from gofra.lexer.tokens import Token
from gofra.types.primitive.void import VoidType


class VariableCannotHasVoidTypeParserError(GofraError):
    def __init__(
        self,
        *args: object,
        varname: str,
        defined_at: Token,
    ) -> None:
        super().__init__(*args)
        self.varname = varname
        self.defined_at = defined_at

    def __repr__(self) -> str:
        return f"""Variable {self.varname} defined at {self.defined_at.location} has {VoidType()} type, which has no size and cannot be used!

[parser-variable-has-void-type]"""
