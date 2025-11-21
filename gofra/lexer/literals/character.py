"""Lexer support for character literals."""

from __future__ import annotations

from typing import TYPE_CHECKING

from gofra.lexer.errors import (
    EmptyCharacterLiteralError,
    ExcessiveCharacterLengthError,
    UnclosedCharacterQuoteError,
)
from gofra.lexer.helpers import (
    find_quoted_literal_end,
    find_word_start,
    unescape_text_literal,
)
from gofra.lexer.tokens import Token, TokenType

if TYPE_CHECKING:
    from gofra.lexer._state import LexerState


CHARACTER_QUOTE = "'"


def tokenize_character_literal(state: LexerState) -> Token:
    """Tokenize character quote at cursor into character literal token or raise error if invalid character."""
    assert state.line and state.line[state.col] == CHARACTER_QUOTE, (  # noqa: PT018
        f"{tokenize_character_literal.__name__} must be called when cursor is at open character quote"
    )

    location = state.current_location()
    state.col += len(CHARACTER_QUOTE)

    close_quote_col = _find_character_literal_end(state) - 1
    if close_quote_col < 0:
        raise UnclosedCharacterQuoteError(open_quote_at=location)

    # Preserve literal as 'X' and unescaped version
    # TODO(@kirillzhosul): Character literal escape messed when trying to escape last quote
    char_literal = state.line[state.col - 1 : close_quote_col + 1]
    char = unescape_text_literal(char_literal.strip(CHARACTER_QUOTE))

    if len(char) == 0:
        raise EmptyCharacterLiteralError(open_quote_at=location)
    if len(char) >= 2:
        raise ExcessiveCharacterLengthError(location, len(char))

    # Advance to next word
    state.col = find_word_start(state.line, close_quote_col + 1)
    return Token(
        type=TokenType.CHARACTER,
        text=char_literal,
        value=ord(char),  # Char-code
        location=location,
    )


def _find_character_literal_end(state: LexerState) -> int:
    return find_quoted_literal_end(state.line, state.col, quote=CHARACTER_QUOTE)
