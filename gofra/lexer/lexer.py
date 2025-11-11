from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from gofra.lexer._state import LexerState
from gofra.lexer.exceptions import (
    LexerAmbiguousHexadecimalAlphabetError,
    LexerEmptyCharacterError,
    LexerExcessiveCharacterLengthError,
    LexerUnclosedCharacterQuoteError,
    LexerUnclosedStringQuoteError,
)
from gofra.lexer.helpers import (
    CHARACTER_QUOTE,
    HEXADECIMAL_MARK,
    SINGLE_LINE_COMMENT,
    STRING_QUOTE,
    find_string_end,
    find_word_end,
    find_word_start,
    is_valid_float,
    is_valid_hexadecimal,
    is_valid_integer,
    unescape_string,
)
from gofra.lexer.keywords import WORD_TO_KEYWORD
from gofra.lexer.tokens import Token, TokenLocation, TokenType

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable
    from pathlib import Path


def tokenize_from_raw(
    source: Path | Literal["cli", "toolchain"],
    iterable: Iterable[str],
) -> Generator[Token]:
    """Stream lexical tokens via generator (perform lexical analysis).

    :returns tokenizer: Generator of tokens, in order from top to bottom of an file (default order)
    """
    state = LexerState(path=source, tokens_buffer=[])

    for row, line in enumerate(iterable, start=0):
        state.line = line

        state.row = row
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

    if symbol == CHARACTER_QUOTE:
        state.col += len(CHARACTER_QUOTE)
        return _tokenize_character_symbol(state)

    if symbol == STRING_QUOTE:
        state.col += len(STRING_QUOTE)
        return _tokenize_string_symbol(state)

    return _tokenize_word_into_token(state)


def _tokenize_string_symbol(state: LexerState) -> Token:
    """Tokenize string symbol into an string."""
    location = state.current_location()

    if (ends_at := find_string_end(state.line, state.col)) is None:
        raise LexerUnclosedStringQuoteError(open_quote_location=location)

    string_unescaped_quoted = state.line[state.col - 1 : ends_at]
    # Unescaped version at current moment is being unused, and probably may be removeD
    string_text = unescape_string(string_unescaped_quoted.strip(STRING_QUOTE))

    state.col = find_word_start(state.line, ends_at)
    return Token(
        type=TokenType.STRING,
        text=string_unescaped_quoted,
        value=string_text,
        location=location,
    )


def _tokenize_character_symbol(state: LexerState) -> Token:
    """Tokenize character symbol into an character."""
    location = state.current_location()

    character_ends_at = state.line.find(CHARACTER_QUOTE, state.col)
    if character_ends_at == -1:
        raise LexerUnclosedCharacterQuoteError(open_quote_location=location)

    character_unescaped_quoted = state.line[state.col - 1 : character_ends_at + 1]
    character = unescape_string(character_unescaped_quoted[1:-1])

    character_len = len(character)
    if character_len == 0:
        raise LexerEmptyCharacterError(open_quote_location=location)
    if character_len != 1:
        raise LexerExcessiveCharacterLengthError(
            excess_begins_at=location,
            excess_by_count=character_len,
        )

    state.col = find_word_start(state.line, character_ends_at + 1)
    return Token(
        type=TokenType.CHARACTER,
        text=character_unescaped_quoted,
        value=ord(character),
        location=location,
    )


def _try_tokenize_numerable_into_token(
    word: str,
    location: TokenLocation,
) -> Token | None:
    """Try to consume given word into number token (integer / float) or return nothing.

    TODO(@kirillzhosul): Review introduction of an unary negation operation (includes negation of non numeric values)
    TODO(@kirillzhosul): Introduce float/decimal numbers
    TODO(@kirillzhosul): Introduce binary base for numeric values
    """
    base = 0
    sign = (1, -1)[word.startswith("-")]
    word = word.removeprefix("-")
    is_fp = False

    if is_valid_integer(word):
        base = 10
    elif word.startswith(HEXADECIMAL_MARK):
        base = 16
        if not is_valid_hexadecimal(word):
            raise LexerAmbiguousHexadecimalAlphabetError(
                hexadecimal_raw=word,
                number_location=location,
            )
    elif is_valid_float(word):
        base = 10
        is_fp = True
    if not base:
        return None

    if is_fp:
        assert base == 10, "FP numbers allowed to be only in base 10"
        return Token(
            type=TokenType.FLOAT,
            text=word,
            value=float(word) * sign,
            location=location,
        )

    return Token(
        type=TokenType.INTEGER,
        text=word,
        value=int(word, base) * sign,
        location=location,
    )


def _tokenize_word_or_keyword_into_tokens(
    state: LexerState,
    word: str,
    location: TokenLocation,
) -> Token:
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

    single_symbols_mapping = {
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
    symbols = "".join(single_symbols_mapping.keys())
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
                type=single_symbols_mapping[char],
                location=location,
                text=char,
                value=char,
                has_trailing_whitespace=False,
            )

        word = word[:symbol_idx]
        state.col = find_word_start(state.line, location.col_number + symbol_idx)

        if token := _try_tokenize_numerable_into_token(word, location):
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

    if token := _try_tokenize_numerable_into_token(word, location):
        return token

    return _tokenize_word_or_keyword_into_tokens(state, word, location)
