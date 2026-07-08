import pytest

from libgofra.lexer._state import LexerState
from libgofra.lexer.errors.unclosed_string_quote import UnclosedStringQuoteError
from libgofra.lexer.literals.string import tokenize_string_literal
from libgofra.lexer.tokens import Token, TokenType


def test_string_literal_tokenize_empty_state() -> None:
    state = LexerState(source="toolchain")
    with pytest.raises(AssertionError):
        tokenize_string_literal(state)


def test_string_literal_tokenize_valid() -> None:
    state = LexerState(source="toolchain")
    state.set_line(0, '"string"')
    _assert_is_string_token(tokenize_string_literal(state))


def test_string_literal_tokenize_unclosed() -> None:
    state = LexerState(source="toolchain")
    state.set_line(0, '"string')

    with pytest.raises(UnclosedStringQuoteError):
        tokenize_string_literal(state)


def test_string_literal_tokenize_unclosed_eol() -> None:
    state = LexerState(source="toolchain")
    state.set_line(0, '"')

    with pytest.raises(UnclosedStringQuoteError):
        tokenize_string_literal(state)


def test_string_literal_tokenize_empty() -> None:
    state = LexerState(source="toolchain")
    state.set_line(0, '""')
    _assert_is_string_token(tokenize_string_literal(state))


def test_string_literal_tokenize_escaped() -> None:
    state = LexerState(source="toolchain")
    state.set_line(0, r'"\r\n"')
    _assert_is_string_token(tokenize_string_literal(state))


@pytest.mark.xfail(reason="Does not work", strict=True)
def test_string_literal_tokenize_escaped_quote() -> None:
    state = LexerState(source="toolchain")
    state.set_line(0, r'"\""')
    _assert_is_string_token(tokenize_string_literal(state))


def _assert_is_string_token(t: Token) -> None:
    assert t.type == TokenType.STRING
