from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


ESCAPE_SYMBOL = "\\"


def unescape_text_literal(string: str) -> str:
    """Remove all terminations within string/char (escape it)."""
    return string.encode().decode("unicode-escape")


def find_word_start(text: str, start: int) -> int:
    """Find start column index of an word."""
    return _find_column(text, start, lambda s: not s.isspace())


def find_word_end(text: str, start: int) -> int:
    """Find end column index of an word."""
    return _find_column(text, start, lambda s: s.isspace())


def find_quoted_literal_end(line: str, idx: int, *, quote: str) -> int:
    """Find index where given string ends (close quote) or -1 if not closed properly."""
    idx_end = len(line)

    prev = line[idx] if idx >= 0 and idx < len(line) else None
    while idx < idx_end:
        current = line[idx]
        if current == quote and prev != ESCAPE_SYMBOL:
            return idx + 1

        prev = current
        idx += 1

    return -1


def _find_column(text: str, start: int, predicate: Callable[[str], bool]) -> int:
    """Find index of an column by predicate. E.g `.index()` but with predicate."""
    end = len(text)
    while start < end and not predicate(text[start]):
        start += 1
    return start
