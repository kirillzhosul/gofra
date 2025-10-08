from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from .tokens import Token, TokenLocation

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=False)
class LexerState:
    """State for lexical analysis which only required for internal usages."""

    path: Path | Literal["cli", "toolchain"]
    tokens_buffer: list[Token]

    row: int = 0
    col: int = 0

    line: str = ""

    def current_location(self) -> TokenLocation:
        if self.path == "cli":
            return TokenLocation.cli()
        if self.path == "toolchain":
            return TokenLocation.toolchain()

        return TokenLocation(
            filepath=self.path,
            line_number=self.row,
            col_number=self.col,
        )
