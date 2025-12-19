from libgofra.lexer.tokens import Token, TokenLocation
from libgofra.preprocessor.exceptions import PreprocessorError


class PreprocessorMacroRedefinesLanguageWordError(PreprocessorError):
    def __init__(self, location: TokenLocation, name: str) -> None:
        self.location = location
        self.name = name

    def __repr__(self) -> str:
        return f"""Macro '{self.name}' at {self.location} tries to redefine language word-definition!"""


class PreprocessorMacroRedefinedError(PreprocessorError):
    def __init__(
        self,
        name: str,
        redefined: TokenLocation,
        original: TokenLocation,
    ) -> None:
        self.name = name
        self.redefined = redefined
        self.original = original

    def __repr__(self) -> str:
        return f"""Redefinition of an macro '{self.name}' at {self.redefined}

Original definition found at {self.original}.

Only single definition allowed for macros.
If it possible scenario of overriding, please un-define before redefinition."""


class PreprocessorMacroNonIdentifierNameError(PreprocessorError):
    def __init__(self, token: Token) -> None:
        self.token = token

    def __repr__(self) -> str:
        return f"""Non-identifier name for macro at {self.token.location}!

Macros should have name as 'identifier' but got '{self.token.type.name}'!"""


class PreprocessorNoMacroNameError(PreprocessorError):
    def __init__(self, location: TokenLocation) -> None:
        self.location = location

    def __repr__(self) -> str:
        return f"""No macro name specified at {self.location}!

Do you have unfinished macro definition?"""
