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

    INTEGER = auto()

    CHARACTER = auto()
    STRING = auto()

    WORD = auto()
    KEYWORD = auto()

    EOL = auto()


@dataclass(frozen=True)
class Token:
    """Lexical token obtained by lexer."""

    type: TokenType

    # Real text of an token within source code
    text: str

    # `pre-parsed` value (e.g numbers are numbers, string are unescaped)
    # This is actually may not be here (inside parser), but due to now this will be as-is
    value: int | str | Keyword | PreprocessorKeyword

    # Location within file
    location: TokenLocation
