from libgofra.exceptions import GofraError
from libgofra.lexer.tokens import Token, TokenType


class ExpectedTokenByParserError(GofraError):
    def __init__(self, *args: object, expected: TokenType, got: Token) -> None:
        super().__init__(*args)
        self.expected = expected
        self.got = got

    def __repr__(self) -> str:
        return f"""Expected {self.expected.name} but got {self.got.type.name} at {self.got.location}!

{self.generic_error_name}"""
