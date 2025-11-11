from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, auto
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from pathlib import Path

    from gofra.lexer.keywords import Keyword, PreprocessorKeyword


@dataclass(frozen=True)
class TokenLocation:
    """Location of any token within source code file."""

    line_number: int
    col_number: int

    filepath: Path | None = None
    source: Literal["file", "cli", "toolchain"] = "file"

    def __post_init__(self) -> None:
        if self.source == "file":
            assert self.filepath is not None

    def __repr__(self) -> str:
        if self.source == "cli":
            return "'(command-line-interface)'"
        if self.source == "toolchain":
            return "'(gofra-toolchain-internals)'"
        assert self.filepath is not None
        return f"'{self.filepath.name}:{self.line_number + 1}:{self.col_number + 1}'"

    def shift_col_number(self, by: int) -> TokenLocation:
        return TokenLocation(
            line_number=self.line_number,
            col_number=self.col_number + by,
            filepath=self.filepath,
            source=self.source,
        )

    @classmethod
    def cli(cls) -> TokenLocation:
        """Create a location for command-line originated tokens."""
        return cls(
            line_number=0,
            col_number=0,
            source="cli",
        )

    @classmethod
    def toolchain(cls) -> TokenLocation:
        """Create a location fo toolchain originated tokens."""
        return cls(
            line_number=0,
            col_number=0,
            source="toolchain",
        )


class TokenType(IntEnum):
    """Type of the lexical token.

    These types is a bit weird due to `convention` but this is a some sort of an legacy code.
    (e.g character/strings/integers must be an literal and parsed at PARSER side)
    https://en.wikipedia.org/wiki/Lexical_analysis
    """

    # Numerical
    INTEGER = auto()
    FLOAT = auto()

    # Text
    CHARACTER = auto()
    STRING = auto()

    # Language
    IDENTIFIER = auto()
    KEYWORD = auto()

    # Brackets and parentheses
    LBRACKET = auto()  # [
    RBRACKET = auto()  # ]
    LPAREN = auto()  # (
    RPAREN = auto()  # )
    LCURLY = auto()  # {
    RCURLY = auto()  # }

    # Additional stuff
    ASSIGNMENT = auto()  # =

    # Punctuation
    DOT = auto()  # .
    COMMA = auto()  # ,
    STAR = auto()  # *
    SEMICOLON = auto()  # ;  (you might need this too)
    COLON = auto()  # :  (you might need this too)
    # Content
    EOF = auto()
    EOL = auto()


@dataclass(frozen=True)
class Token:
    """Lexical token obtained by lexer."""

    type: TokenType

    # Real text of an token within source code
    text: str

    # `pre-parsed` value (e.g numbers are numbers, string are unescaped)
    # This is actually may not be here (inside parser), but due to now this will be as-is
    value: int | float | str | Keyword | PreprocessorKeyword

    # Location within file
    location: TokenLocation

    has_trailing_whitespace: bool = True
