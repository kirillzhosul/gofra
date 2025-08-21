from dataclasses import dataclass
from pathlib import Path

from .tokens import TokenLocation


@dataclass(frozen=False)
class LexerState:
    """State for lexical analysis which only required for internal usages."""

    path: Path

    row: int = 0
    col: int = 0

    line: str = ""

    def current_location(self) -> TokenLocation:
        return TokenLocation(
            filepath=self.path,
            line_number=self.row,
            col_number=self.col,
        )
