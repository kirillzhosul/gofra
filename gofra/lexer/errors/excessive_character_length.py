from gofra.exceptions import GofraError
from gofra.lexer.tokens import TokenLocation


class ExcessiveCharacterLengthError(GofraError):
    def __init__(self, open_quote_at: TokenLocation, excess_by_count: int) -> None:
        self.open_quote_at = open_quote_at
        self.excess_by_count = excess_by_count

    def __repr__(self) -> str:
        return f"""Excessive character literal length at {self.open_quote_at}!

Expected only one *symbol* in character literal but got {self.excess_by_count}!

Did you accidentally mix up character and string literal?
Character literals are single symbol (unless escaping)

{self.generic_error_name}"""
