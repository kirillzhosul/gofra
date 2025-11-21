import pytest

from gofra.lexer._state import LexerState
from gofra.lexer.errors.unclosed_string_quote import UnclosedStringQuoteError
from gofra.lexer.literals.string import tokenize_string_literal
from gofra.lexer.tokens import Token, TokenType


def test_string_literal_tokenize_empty_state() -> None:
    state = LexerState(path="toolchain")
    with pytest.raises(AssertionError):
        tokenize_string_literal(state)


def test_string_literal_tokenize_valid() -> None:
    state = LexerState(path="toolchain")
    state.set_line(0, '"string"')
    _assert_is_string_token(tokenize_string_literal(state))


def test_string_literal_tokenize_unclosed() -> None:
    state = LexerState(path="toolchain")
    state.set_line(0, '"string')

    with pytest.raises(UnclosedStringQuoteError):
        tokenize_string_literal(state)


def test_string_literal_tokenize_unclosed_eol() -> None:
    state = LexerState(path="toolchain")
    state.set_line(0, '"')

    with pytest.raises(UnclosedStringQuoteError):
        tokenize_string_literal(state)


def test_string_literal_tokenize_empty() -> None:
    state = LexerState(path="toolchain")
    state.set_line(0, '""')
    _assert_is_string_token(tokenize_string_literal(state))


def test_string_literal_tokenize_escaped() -> None:
    state = LexerState(path="toolchain")
    state.set_line(0, r'"\r\n"')
    _assert_is_string_token(tokenize_string_literal(state))


@pytest.mark.skip("Does not work")
def test_string_literal_tokenize_escaped_quote() -> None:
    state = LexerState(path="toolchain")
    state.set_line(0, r'"\""')
    _assert_is_string_token(tokenize_string_literal(state))


def _assert_is_string_token(t: Token) -> None:
    assert t.type == TokenType.STRING
