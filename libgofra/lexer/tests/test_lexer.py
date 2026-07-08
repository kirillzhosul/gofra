import pytest

from libgofra.lexer.lexer import tokenize_from_raw
from libgofra.lexer.tokens import TokenType


def test_inline_comment() -> None:
    assert_token_types(
        "id // some comment 123 id",
        expected=[TokenType.IDENTIFIER],
    )


def test_simple_characters() -> None:
    assert_token_types("'b'", expected=[TokenType.CHARACTER])
    assert_token_types("'2'", expected=[TokenType.CHARACTER])
    assert_token_types("'\\n'", expected=[TokenType.CHARACTER])
    assert_token_types("'\\t'", expected=[TokenType.CHARACTER])
    assert_token_types("' '", expected=[TokenType.CHARACTER])
    assert_token_types("'/'", expected=[TokenType.CHARACTER])


def test_simple_float_numbers() -> None:
    assert_token_types("1.0", expected=[TokenType.FLOAT])
    assert_token_types("4123.213", expected=[TokenType.FLOAT])
    assert_token_types("-24.01", expected=[TokenType.FLOAT])


def test_negative_float_numbers() -> None:
    assert next(iter(tokenize_from_raw("cli", lines=["-24.01"]))).value == -24.01


def test_negative_integer_numbers() -> None:
    assert_token_types(
        "-12312412415614632412312312312312316",
        expected=[TokenType.INTEGER],
    )

    assert_token_types("-100", expected=[TokenType.INTEGER])


def test_simple_integer_numbers() -> None:
    assert_token_types("0", expected=[TokenType.INTEGER])
    assert_token_types("123", expected=[TokenType.INTEGER])
    assert_token_types("10540", expected=[TokenType.INTEGER])

    assert_token_types(
        "1235812835182358123851823581238518235",
        expected=[TokenType.INTEGER],
    )


@pytest.mark.xfail(
    reason="Bug for now",
    strict=True,
)  # TODO(@kirillzhosul): unsupported for now
def test_escaped_inline_character_quote() -> None:
    assert_token_types("'\\\\'", expected=[TokenType.CHARACTER])


def test_eof_after_each_line() -> None:
    assert_token_types(
        "x",
        "y",
        expected=[
            TokenType.IDENTIFIER,
            TokenType.EOL,
            TokenType.IDENTIFIER,
            TokenType.EOL,
            TokenType.EOF,
        ],
        implicit_eol_eof=False,
    )


def assert_token_types(
    *source: str,
    expected: list[TokenType],
    implicit_eol_eof: bool = True,
) -> None:
    tokens = list(tokenize_from_raw("cli", lines=source))
    if implicit_eol_eof:
        expected += [TokenType.EOL, TokenType.EOF]
    assert [token.type for token in tokens] == expected
