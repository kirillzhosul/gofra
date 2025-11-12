from gofra.exceptions import GofraError
from gofra.lexer.tokens import TokenLocation


class UnknownPrimitiveTypeError(GofraError):
    def __init__(self, typename: str, at: TokenLocation) -> None:
        self.typename = typename
        self.at = at

    def __repr__(self) -> str:
        return f"""Unknown type '{self.typename}'!

Expected known primitive type at {self.at} but got unknown '{self.typename}'
Expected either an primitive type, aliased type, or structure name!
(Or variable references in some expressions)

{self.generic_error_name}"""
