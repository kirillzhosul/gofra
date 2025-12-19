from string import digits, hexdigits

from libgofra.lexer.errors.ambiguous_hexadecimal_alphabet import (
    AmbiguousHexadecimalAlphabetError,
)
from libgofra.lexer.tokens import Token, TokenLocation, TokenType

HEXADECIMAL_MARK = "0x"


def is_valid_hexadecimal(text: str) -> bool:
    """Is given raw text cans be parsed as hexadecimal?."""
    return all(c in hexdigits for c in text[len(HEXADECIMAL_MARK) :])


def is_valid_integer(text: str) -> bool:
    """Is given raw text can be parsed as integer?."""
    return text.isdigit()


def is_valid_float(text: str) -> bool:
    """Is given raw text can be parsed as integer?."""
    if text.count(".") != 1:
        return False

    # Yes, `isdecimal` is easier
    whole, fractional = text.split(".", maxsplit=1)
    return whole.isdigit() and fractional.isdigit()


def try_tokenize_numerable_into_token(
    word: str,
    location: TokenLocation,
) -> Token | None:
    """Try to consume given word into number token (integer / float) or return nothing.

    TODO(@kirillzhosul): Review introduction of an unary negation operation (includes negation of non numeric values)
    TODO(@kirillzhosul): Introduce float/decimal numbers
    TODO(@kirillzhosul): Introduce binary base for numeric values
    TODO(@kirillzhosul): Refactor
    """
    if not word.startswith(("-", *digits)):
        return None

    base = 0
    sign = (1, -1)[word.startswith("-")]
    word = word.removeprefix("-")
    is_fp = False

    if is_valid_integer(word):
        base = 10
    elif word.startswith(HEXADECIMAL_MARK):
        base = 16
        if not is_valid_hexadecimal(word):
            raise AmbiguousHexadecimalAlphabetError(
                at=location,
                number_raw=word,
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
