import pytest

from libgofra.lexer._state import LexerState
from libgofra.lexer.errors.empty_character_literal import EmptyCharacterLiteralError
from libgofra.lexer.errors.excessive_character_length import (
    ExcessiveCharacterLengthError,
)
from libgofra.lexer.errors.unclosed_character_quote import UnclosedCharacterQuoteError
from libgofra.lexer.literals.character import tokenize_character_literal
from libgofra.lexer.tokens import Token, TokenType


def test_character_literal_tokenize_empty_state() -> None:
    state = LexerState(source="toolchain")
    with pytest.raises(AssertionError):
        tokenize_character_literal(state)


def test_character_literal_tokenize_valid() -> None:
    state = LexerState(source="toolchain")
    state.set_line(0, "'a'")
    _assert_is_character_token(tokenize_character_literal(state))


def test_character_literal_tokenize_unclosed() -> None:
    state = LexerState(source="toolchain")
    state.set_line(0, "'a")
    with pytest.raises(UnclosedCharacterQuoteError):
        tokenize_character_literal(state)


def test_character_literal_tokenize_excessive() -> None:
    state = LexerState(source="toolchain")
    state.set_line(0, "'abc'")
    with pytest.raises(ExcessiveCharacterLengthError):
        tokenize_character_literal(state)


def test_character_literal_tokenize_empty() -> None:
    state = LexerState(source="toolchain")
    state.set_line(0, "''")
    with pytest.raises(EmptyCharacterLiteralError):
        tokenize_character_literal(state)


def test_character_literal_tokenize_escaped() -> None:
    state = LexerState(source="toolchain")
    state.set_line(0, r"'\n'")
    _assert_is_character_token(tokenize_character_literal(state))


@pytest.mark.xfail(reason="Does not work", strict=True)
def test_character_literal_tokenize_escaped_quote() -> None:
    state = LexerState(source="toolchain")
    state.set_line(0, r"'\\'")
    _assert_is_character_token(tokenize_character_literal(state))


def _assert_is_character_token(t: Token) -> None:
    assert t.type == TokenType.CHARACTER
