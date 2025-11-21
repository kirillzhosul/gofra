"""Errors collections that lexer may raise (user-facing ones)."""

from .ambiguous_hexadecimal_alphabet import AmbiguousHexadecimalAlphabetError
from .empty_character_literal import EmptyCharacterLiteralError
from .excessive_character_length import ExcessiveCharacterLengthError
from .unclosed_character_quote import UnclosedCharacterQuoteError
from .unclosed_string_quote import UnclosedStringQuoteError

__all__ = [
    "AmbiguousHexadecimalAlphabetError",
    "EmptyCharacterLiteralError",
    "ExcessiveCharacterLengthError",
    "UnclosedCharacterQuoteError",
    "UnclosedStringQuoteError",
]
