from __future__ import annotations

from typing import TYPE_CHECKING

from gofra.lexer.keywords import PreprocessorKeyword
from gofra.lexer.tokens import Token, TokenType

from ._state import PreprocessorState
from .conditions import resolve_conditional_block_from_token
from .include import resolve_include_from_token_into_state
from .macros.preprocessor import (
    consume_macro_definition_from_token,
    consume_macro_undefine_from_token,
    try_resolve_and_expand_macro_reference_from_token,
)

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable
    from pathlib import Path

    from gofra.preprocessor.macros import MacrosRegistry


def preprocess_file(
    path: Path,
    lexer: Generator[Token],
    include_search_paths: Iterable[Path],
    macros: MacrosRegistry,
) -> Generator[Token]:
    """Preprocess given lexer token stream by resolving includes, CTE/macros.

    Simply, wraps an lexer into another `lexer` and preprocess on the fly.
    """
    state = PreprocessorState(
        path=path,
        lexer=lexer,
        macros=macros,
        include_search_paths=include_search_paths,
    )

    for token in state.tokenizer:
        print(token)
        match token:
            case Token(type=TokenType.KEYWORD, value=PreprocessorKeyword.INCLUDE):
                resolve_include_from_token_into_state(token, state)
            case Token(type=TokenType.KEYWORD, value=PreprocessorKeyword.DEFINE):
                consume_macro_definition_from_token(token, state)
            case (
                Token(type=TokenType.KEYWORD, value=PreprocessorKeyword.IF_DEFINED)
                | Token(
                    type=TokenType.KEYWORD,
                    value=PreprocessorKeyword.IF_NOT_DEFINED,
                )
            ):
                resolve_conditional_block_from_token(token, state)
            case Token(type=TokenType.KEYWORD, value=PreprocessorKeyword.UNDEFINE):
                consume_macro_undefine_from_token(token, state)
            case Token(type=TokenType.IDENTIFIER):
                if try_resolve_and_expand_macro_reference_from_token(token, state):
                    continue
                yield token
            case Token(type=TokenType.KEYWORD, value=PreprocessorKeyword.END_IF):
                # We dont yield preprocessor endif as preprocessor will resolve it by itself via conditional block resolver
                pass
            case Token(type=TokenType.EOL):
                # EOL is usable only by preprocessor, so we drop that
                pass
            case _:
                yield token
