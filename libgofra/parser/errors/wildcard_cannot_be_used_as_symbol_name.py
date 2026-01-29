from libgofra.exceptions import GofraError
from libgofra.lexer.tokens import TokenLocation


class WildcardCannotBeUsedAsSymbolNameError(GofraError):
    def __init__(self, at: TokenLocation) -> None:
        self.at = at

    def __repr__(self) -> str:
        return f"""Wildcard `_` cannot be used as identifier here!

Tried to use `_` as symbol name at {self.at}, which is prohibited
It is only allowed as param name (for now) to mark it as never used/usable

{self.generic_error_name}"""
