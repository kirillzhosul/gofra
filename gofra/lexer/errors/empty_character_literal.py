from gofra.exceptions import GofraError
from gofra.lexer.tokens import TokenLocation


class EmptyCharacterLiteralError(GofraError):
    def __init__(self, open_quote_at: TokenLocation) -> None:
        self.open_quote_at = open_quote_at

    def __repr__(self) -> str:
        return f"""Empty character literal at {self.open_quote_at}!

Expected single *symbol* in character literal but got nothing!
Did you forgot to enter character?

{self.generic_error_name}"""
