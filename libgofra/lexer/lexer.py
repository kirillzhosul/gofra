from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from libgofra.lexer._state import LexerState
from libgofra.lexer.helpers import (
    find_word_end,
    find_word_start,
)
from libgofra.lexer.keywords import WORD_TO_KEYWORD
from libgofra.lexer.literals.character import tokenize_character_literal
from libgofra.lexer.literals.numeric import try_tokenize_numerable_into_token
from libgofra.lexer.literals.string import tokenize_string_literal
from libgofra.lexer.tokens import Token, TokenLocation, TokenType

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable
    from pathlib import Path


SINGLE_LINE_COMMENT = "//"


def tokenize_from_raw(
    source: Path | Literal["cli", "toolchain"],
    lines: Iterable[str],
) -> Generator[Token]:
    """Stream lexical tokens via generator (perform lexical analysis).

    :returns tokenizer: Generator of tokens, in order from top to bottom of an file (default order)
    """
    state = LexerState(path=source)

    for row, line in enumerate(lines, start=0):
        state.set_line(row, line)

        state.col = find_word_start(line, 0)

        col_ends_at = len(state.line)
        while state.col < col_ends_at and (token := _tokenize_line_next_token(state)):
            yield token

        yield Token(
            type=TokenType.EOL,
            text="\n",
            value=0,
            location=state.current_location(),
        )

    yield Token(
        type=TokenType.EOF,
        text="\n",
        value=0,
        location=state.current_location(),
    )


def _tokenize_line_next_token(state: LexerState) -> Token | None:
    """Acquire token from current state and modify it to apply next tokenize, or None if reached end (EOL/EOF).

    :returns token: Token from state or None if state must go to the next line (no tokens).
    """
    # First symbol of an token, as we exclusively tokenize character/string tokens due to their fixed/variadic length.
    symbol = state.line[state.col]

    match symbol:
        case "'":
            return tokenize_character_literal(state)
        case '"':
            return tokenize_string_literal(state)
        case _:
            return _tokenize_word_into_token(state)


SINGLE_SYMBOLS_MAPPING = {
    "[": TokenType.LBRACKET,
    "]": TokenType.RBRACKET,
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    ",": TokenType.COMMA,
    ".": TokenType.DOT,
    ";": TokenType.SEMICOLON,
    "=": TokenType.ASSIGNMENT,
    ":": TokenType.COLON,
    "{": TokenType.LCURLY,
    "}": TokenType.RCURLY,
    "*": TokenType.STAR,
}


def _tokenize_word_or_keyword_into_tokens(
    state: LexerState,
    word: str,
    location: TokenLocation,
) -> Token | None:
    """Tokenize base word symbol into an word or keyword."""
    if keyword := WORD_TO_KEYWORD.get(word):
        return Token(
            type=TokenType.KEYWORD,
            text=word,
            location=location,
            value=keyword,
        )

    # From that moment we have straightforward identifier (e.g an word) or an composite identifier
    # for example parenthesised identifier(s): identifier(identifier) where () can be [] as parenthesis

    symbols = "".join(SINGLE_SYMBOLS_MAPPING.keys())
    if any(c in symbols for c in word):
        symbol_idx = min(word.index(c) for c in symbols if c in word)

        if word[symbol_idx] == "=" and word != "=":
            # Weirdest workaround for assignment composite token construction
            # should be refactored ASAP
            # assignment operator
            return Token(
                type=TokenType.IDENTIFIER,
                text=word,
                location=location,
                value=word,
            )

        if symbol_idx == 0:
            # Skip beginning with symbol to next symbol - single symbol
            state.col = find_word_start(state.line, location.col_number + 1)
            char = word[0]

            return Token(
                type=SINGLE_SYMBOLS_MAPPING[char],
                location=location,
                text=char,
                value=char,
                has_trailing_whitespace=False,
            )

        word = word[:symbol_idx]
        state.col = find_word_start(state.line, location.col_number + symbol_idx)

        if token := try_tokenize_numerable_into_token(word, location):
            return token

        return Token(
            type=TokenType.IDENTIFIER,
            location=location,
            text=word,
            value=word,
        )

    return Token(
        type=TokenType.IDENTIFIER,
        text=word,
        location=location,
        value=word,
    )


def _tokenize_word_into_token(state: LexerState) -> Token | None:
    """Consumes `word` (e.g can be also an number) into token (non-string and non-character as must be handled above).

    :returns token: Token or None if should skip this line due to EOL as comment mark found.
    """
    word_ends_at = find_word_end(state.line, state.col)
    word = state.line[state.col : word_ends_at]

    if word.startswith(SINGLE_LINE_COMMENT):
        # Next words were prefixed with comment mark - skip whole line.
        return None

    # Remember current location and jump to next word for next() call.
    location = state.current_location()
    state.col = find_word_start(state.line, word_ends_at)

    if token := try_tokenize_numerable_into_token(word, location):
        return token

    return _tokenize_word_or_keyword_into_tokens(state, word, location)


def debug_lexer_wrapper(lexer: Generator[Token]) -> Generator[Token]:
    for token in lexer:
        print(token.type.name, token.value, token.location)
        yield token
