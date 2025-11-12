from gofra.exceptions import GofraError
from gofra.lexer.keywords import Keyword
from gofra.lexer.tokens import Token


class KeywordInWithoutLoopBlockError(GofraError):
    def __init__(self, token: Token) -> None:
        self.token = token

    def __repr__(self) -> str:
        assert isinstance(self.token.value, Keyword)
        return f"""Keyword 'IN' used without context.

Keyword '{Keyword.IN.name}' at {self.token.location} is used without context.
This keyword must only appear in form of '{Keyword.FOR.name}'!

{self.generic_error_name}"""
