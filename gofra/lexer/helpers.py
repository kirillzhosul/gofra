from __future__ import annotations

from string import hexdigits
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


STRING_QUOTE = '"'
CHARACTER_QUOTE = "'"
SINGLE_LINE_COMMENT = "//"
HEXADECIMAL_MARK = "0x"
ESCAPE_SYMBOL = "\\"


def unescape_string(string: str) -> str:
    """Remove all terminations within string (escape it)."""
    return string.encode("unicode_escape").decode("UTF-8")


def is_valid_hexadecimal(text: str) -> bool:
    """Is given raw text cans be parsed as hexadecimal?."""
    return all(c in hexdigits for c in text[len(HEXADECIMAL_MARK) :])


def is_valid_integer(text: str) -> bool:
    """Is given raw text can be parsed as integer?."""
    return text.isdigit()


def find_word_start(text: str, start: int) -> int:
    """Find start column index of an word."""
    return _find_column(text, start, lambda s: not s.isspace())


def find_word_end(text: str, start: int) -> int:
    """Find end column index of an word."""
    return _find_column(text, start, str.isspace)


def find_string_end(string: str, start: int) -> int | None:
    """Find index where given string ends (close quote) or None if not closed properly."""
    idx = start
    idx_end = len(string)

    prev = string[idx]

    while idx < idx_end:
        current = string[idx]
        if current == STRING_QUOTE and prev != ESCAPE_SYMBOL:
            break

        prev = current
        idx += 1

    if idx >= idx_end:
        return None
    return idx + 1


def _find_column(text: str, start: int, predicate: Callable[[str], bool]) -> int:
    """Find index of an column by predicate. E.g `.index()` but with predicate."""
    end = len(text)
    while start < end and not predicate(text[start]):
        start += 1
    return start
