from gofra.exceptions import GofraError
from gofra.lexer.tokens import TokenLocation
from gofra.types._base import Type


class TypeHasNoCompileTimeInitializerParserError(GofraError):
    def __init__(
        self,
        type_with_no_initializer: Type,
        varname: str,
        at: TokenLocation,
    ) -> None:
        self.type_with_no_initializer = type_with_no_initializer
        self.at = at
        self.varname = varname

    def __repr__(self) -> str:
        return f"""No known initializer for type '{self.type_with_no_initializer}'!

Variable '{self.varname}' defined at {self.at} has 
type '{self.type_with_no_initializer}' has no initializer known at compile time!
Has no known solution to initialize this variable.

Consider using manual initializer logic.

{self.generic_error_name}"""
