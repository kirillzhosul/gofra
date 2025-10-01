from __future__ import annotations

from typing import TYPE_CHECKING

from gofra.exceptions import GofraError

if TYPE_CHECKING:
    from gofra.lexer.tokens import Token


class ParserFunctionIsBothInlineAndExternalError(GofraError):
    def __init__(self, *args: object, modifier_token: Token) -> None:
        super().__init__(*args)
        self.modifier_token = modifier_token

    def __repr__(self) -> str:
        return f"""Tried to define function that is both `external` and `inline`.
Found at: {self.modifier_token.location}

External function cannot have an body and defined outside, 
which leads to behavior for `extern inline` function unknown and prohibited"""


class ParserFunctionModifierReappliedError(GofraError):
    def __init__(self, *args: object, modifier_token: Token) -> None:
        super().__init__(*args)
        self.modifier_token = modifier_token

    def __repr__(self) -> str:
        return f"""Function modifier reapplied.
Found at: {self.modifier_token.location}

There is no need to reapply same function modifier."""


class ParserExpectedFunctionAfterFunctionModifiersError(GofraError):
    def __init__(self, *args: object, modifier_token: Token) -> None:
        super().__init__(*args)
        self.modifier_token = modifier_token

    def __repr__(self) -> str:
        return f"""Expected function keyword after function modifiers (`inline`, `extern`).
But last token at {self.modifier_token.location} is not an function keyword!

Function modifiers must be followed by function keyword."""


class ParserExpectedFunctionReturnTypeError(GofraError):
    def __init__(self, *args: object, definition_token: Token) -> None:
        super().__init__(*args)
        self.definition_token = definition_token

    def __repr__(self) -> str:
        return f"""Expected function return type at {self.definition_token.location}.

Do you have unfinished function definition?"""


class ParserFunctionNoNameError(GofraError):
    def __init__(self, *args: object, token: Token) -> None:
        super().__init__(*args)
        self.token = token

    def __repr__(self) -> str:
        return f"""Expected function name with signature at {self.token.location}!

Do you have unfinished function definition?"""


class ParserExpectedFunctionKeywordError(GofraError):
    def __init__(self, *args: object, token: Token) -> None:
        super().__init__(*args)
        self.token = token

    def __repr__(self) -> str:
        return f"""Expected function keyword at {self.token.location}!

But got something else.
Do you have unfinished function definition?"""


class ParserFunctionInvalidTypeError(GofraError):
    def __init__(self, *args: object, type_token: Token, requested_type: str) -> None:
        super().__init__(*args)
        self.type_token = type_token
        self.requested_type = requested_type

    def __repr__(self) -> str:
        return f"""Unknown type `{self.requested_type}` used in function definition at {self.type_token.location}.

Expected one of known types"""
