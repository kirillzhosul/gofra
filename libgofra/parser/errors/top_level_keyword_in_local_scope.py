from libgofra.exceptions import GofraError
from libgofra.lexer.keywords import Keyword
from libgofra.lexer.tokens import Token


class TopLevelKeywordInLocalScopeError(GofraError):
    def __init__(self, token: Token) -> None:
        self.token = token

    def __repr__(self) -> str:
        assert isinstance(self.token.value, Keyword)
        return f"""Top-level keyword used in local scope!

Keyword '{self.token.value.name}' at {self.token.location} is root-only and cannot be used inside any local scope!

{self.generic_error_name}"""
