"""Lexer support for string literals."""

from __future__ import annotations

from typing import TYPE_CHECKING

from gofra.lexer.errors import UnclosedStringQuoteError
from gofra.lexer.helpers import (
    find_quoted_literal_end,
    find_word_start,
    unescape_text_literal,
)
from gofra.lexer.tokens import Token, TokenType

if TYPE_CHECKING:
    from gofra.lexer._state import LexerState


STRING_QUOTE = '"'


def tokenize_string_literal(state: LexerState) -> Token:
    """Tokenize string quote at cursor into string literal token or raise error if invalid string."""
    assert state.line and state.line[state.col] == STRING_QUOTE, (  # noqa: PT018
        f"{tokenize_string_literal.__name__} must be called when cursor is at open string quote"
    )

    location = state.current_location()
    state.col += len(STRING_QUOTE)

    ends_at = _find_string_literal_end(state)
    if ends_at == -1:
        raise UnclosedStringQuoteError(location)

    # Preserve literal as "abc" and unescaped version
    # TODO(@kirillzhosul): String literal escape messed when trying to escape last quote
    string_literal = state.line[state.col - 1 : ends_at]
    string_text = unescape_text_literal(string_literal.strip(STRING_QUOTE))

    # Advance to next word
    state.col = find_word_start(state.line, ends_at)
    return Token(
        type=TokenType.STRING,
        text=string_literal,
        value=string_text,
        location=location,
    )


def _find_string_literal_end(state: LexerState) -> int:
    return find_quoted_literal_end(state.line, state.col, quote=STRING_QUOTE)
