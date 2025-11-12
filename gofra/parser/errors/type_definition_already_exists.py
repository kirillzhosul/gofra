from gofra.exceptions import GofraError
from gofra.lexer.tokens import TokenLocation


class TypeDefinitionAlreadyExistsError(GofraError):
    def __init__(self, typename: str, redefined_at: TokenLocation) -> None:
        self.typename = typename
        self.redefined_at = redefined_at

    def __repr__(self) -> str:
        return f"""Type '{self.typename}' already defined!

Tried to redefine type '{self.typename}' at {self.redefined_at}
This type is already defined!

{self.generic_error_name}"""
