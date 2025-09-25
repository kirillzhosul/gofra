from gofra.lexer.tokens import Token, TokenLocation, TokenType
from gofra.preprocessor.exceptions import PreprocessorError
from gofra.preprocessor.macros.macro import Macro


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
If it possible scenatio of overriding, please un-define before redefinition."""


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


class PreprocessorMacroContainsKeywordError(PreprocessorError):
    def __init__(self, macro: Macro, keyword: Token) -> None:
        self.macro = macro
        self.keyword = keyword
        assert self.keyword.type == TokenType.KEYWORD

    def __repr__(self) -> str:
        return f"""Macro '{self.macro.name}' at {self.macro.location} contains keyword `{self.keyword.text}` inside, at {self.keyword.location}!

Macro cannot contain keywords inside their bodies.
Alternative possible approach is to use `inline` functions."""
