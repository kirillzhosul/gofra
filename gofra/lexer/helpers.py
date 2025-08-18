from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


def unescape_string(string: str) -> str:
    """Remove all terminations within string."""
    return (
        string.encode("UTF-8")
        .decode("unicode_escape")
        .encode("latin-1")
        .decode("UTF-8")
    )


def _find_column(text: str, start: int, predicate: Callable[[str], bool]) -> int:
    end = len(text)
    while start < end and not predicate(text[start]):
        start += 1
    return start


def find_word_start(text: str, start: int) -> int:
    return _find_column(text, start, lambda s: not s.isspace())


def find_word_end(text: str, start: int) -> int:
    return _find_column(text, start, str.isspace)


def find_string_end(string: str, start: int) -> int | None:
    idx = start
    idx_end = len(string)

    prev = string[idx]

    while idx < idx_end:
        current = string[idx]
        if current == '"' and prev != "\\":
            break

        prev = current
        idx += 1

    if idx >= idx_end:
        return None
    return idx
