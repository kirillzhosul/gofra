from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class TokenLocation:
    """Location of any token within source code file."""

    filepath: Path
    line_number: int
    col_number: int

    def __repr__(self) -> str:
        return f"'{self.filepath.name}:{self.line_number + 1}:{self.col_number + 1}'"


class TokenType(IntEnum):
    """Type of the lexical token.

    These types is a bit weird due to `convention` but this is a some sort of an legacy code.
    (e.g character/strings/integers must be an literal and parsed at PARSER side)
    https://en.wikipedia.org/wiki/Lexical_analysis
    """

    INTEGER = auto()

    CHARACTER = auto()
    STRING = auto()

    WORD = auto()
    KEYWORD = auto()


@dataclass(frozen=True)
class Token:
    """Lexical token obtained by lexer."""

    type: TokenType

    # Real text of an token within source code
    text: str

    # `pre-parsed` value (e.g numbers are numbers, string are unescaped)
    # This is actually may not be here (inside parser), but due to now this will be as-is
    value: int | str

    # Location within file
    location: TokenLocation
