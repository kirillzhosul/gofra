from gofra.exceptions import GofraError
from gofra.lexer.tokens import TokenLocation


class UnclosedStringQuoteError(GofraError):
    def __init__(self, open_quote_at: TokenLocation) -> None:
        self.open_quote_at = open_quote_at

    def __repr__(self) -> str:
        return f"""Unclosed string quote at {self.open_quote_at}!

Did you forgot to close string or mistyped string quote?
Multi-line strings are prohibited, if this was your intention

{self.generic_error_name}"""
