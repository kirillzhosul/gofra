from gofra.exceptions import GofraError
from gofra.lexer.keywords import Keyword
from gofra.lexer.tokens import Token


class LocalLevelKeywordInGlobalScopeError(GofraError):
    def __init__(self, token: Token) -> None:
        self.token = token

    def __repr__(self) -> str:
        assert isinstance(self.token.value, Keyword)
        return f"""Local-level keyword used in global scope!

Keyword '{self.token.value.name}' at {self.token.location} is local-only and cannot be used inside global scope!

{self.generic_error_name}"""
