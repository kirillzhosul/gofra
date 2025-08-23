from collections import deque
from collections.abc import Generator, Iterable, MutableMapping
from pathlib import Path

from gofra.lexer import Token

from .macros import Macro


class PreprocessorState:
    """State of an preprocessor stage."""

    # Current file which is being processed
    path: Path

    # Lexical token streams from lexer or preprocessor itself
    # by default first is one from lexer and then it is extended by preprocessor to also consume next tokens from it until exhausted
    tokenizers: deque[Generator[Token]]

    # Remember which paths was included to not include them again.
    already_included_paths: list[Path]

    # Where to additionally search for paths
    include_search_paths: Iterable[Path]

    macros: MutableMapping[str, Macro]

    def __init__(
        self,
        path: Path,
        lexer: Generator[Token],
        include_search_paths: Iterable[Path],
    ) -> None:
        self.path = path.resolve(strict=True)

        self.include_search_paths = include_search_paths
        self.already_included_paths = [path]

        self.macros = {}

        self.tokenizers = deque((lexer,))
        self.tokenizer = self.iterate_tokenizers()

    def iterate_tokenizers(self) -> Generator[Token]:
        """Consume tokens from each tokenizers until all exhausted."""
        while self.tokenizers:
            # Consume token from current (last) tokenizer
            tokenizer = self.tokenizers[-1]
            token = next(tokenizer, None)

            if token:
                yield token
                continue

            # Current tokenizer exhausted and must be removed
            self.tokenizers.pop()
