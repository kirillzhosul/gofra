from gofra.exceptions import GofraError
from gofra.lexer.tokens import Token


class TypecastExpectedTypenameIdentifierParserError(GofraError):
    def __init__(self, *args: object, token: Token) -> None:
        super().__init__(*args)
        self.token = token

    def __repr__(self) -> str:
        return f"""Expected typename tokens after `typecast` at {self.token.location} but found {self.token.type.name}"""
