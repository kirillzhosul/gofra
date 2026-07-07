"""Errors collections that lexer may raise (user-facing ones)."""

from .ambiguous_hexadecimal_alphabet import AmbiguousHexadecimalAlphabetError
from .empty_character_literal import EmptyCharacterLiteralError
from .excessive_character_length import ExcessiveCharacterLengthError
from .io_file_does_not_exists import IOFileDoesNotExistsError
from .io_file_not_an_file import IOFileNotAnFileError
from .io_file_not_an_text_file import IOFileNotAnTextFileError
from .unclosed_character_quote import UnclosedCharacterQuoteError
from .unclosed_string_quote import UnclosedStringQuoteError

__all__ = [
    "AmbiguousHexadecimalAlphabetError",
    "EmptyCharacterLiteralError",
    "ExcessiveCharacterLengthError",
    "IOFileDoesNotExistsError",
    "IOFileNotAnFileError",
    "IOFileNotAnTextFileError",
    "UnclosedCharacterQuoteError",
    "UnclosedStringQuoteError",
]
