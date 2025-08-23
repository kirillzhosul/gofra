from __future__ import annotations

from typing import TYPE_CHECKING

from gofra.lexer.keywords import Keyword
from gofra.lexer.tokens import Token, TokenType

from ._state import PreprocessorState
from .include import (
    resolve_include_from_token_into_state,
)
from .macros.preprocessor import (
    define_macro_block_from_token,
    try_resolve_macro_reference_from_token,
)

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable
    from pathlib import Path


def preprocess_file(
    path: Path,
    lexer: Generator[Token],
    include_search_paths: Iterable[Path],
) -> Generator[Token]:
    """Preprocess given lexer token stream by resolving includes, CTE/macros.

    Simply, wraps an lexer into another `lexer` and preprocess on the fly.
    """
    state = PreprocessorState(
        path=path,
        lexer=lexer,
        include_search_paths=include_search_paths,
    )

    for token in state.tokenizer:
        match token:
            case Token(type=TokenType.KEYWORD, value=Keyword.INCLUDE):
                resolve_include_from_token_into_state(token, state)
            case Token(type=TokenType.KEYWORD, value=Keyword.MACRO):
                define_macro_block_from_token(token, state)
            case Token(type=TokenType.WORD):
                if try_resolve_macro_reference_from_token(token, state):
                    continue
                yield token
            case _:
                yield token
