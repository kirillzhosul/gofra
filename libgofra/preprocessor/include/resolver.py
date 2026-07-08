from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from libgofra.import_path_resolver import try_resolve_and_find_real_include_path
from libgofra.lexer.io import open_source_file_line_stream
from libgofra.lexer.keywords import PreprocessorKeyword
from libgofra.lexer.lexer import tokenize_from_raw
from libgofra.lexer.tokens import Token, TokenType

from .exceptions import (
    PreprocessorIncludeCurrentFileError,
    PreprocessorIncludeFileNotFoundError,
    PreprocessorIncludeNonStringNameError,
    PreprocessorIncludeNoPathError,
)

if TYPE_CHECKING:
    from libgofra.preprocessor._state import PreprocessorState


def resolve_include_from_token_into_state(
    include_token: Token,
    state: PreprocessorState,
) -> None:
    """Consume and resolve include construction into real include at preprocessor side, omitting include if already included."""
    requested_include_path = _consume_include_raw_path_from_token(include_token, state)
    if requested_include_path.resolve(strict=False) == state.path:
        raise PreprocessorIncludeCurrentFileError(include_path_token=include_token)

    msg = "Include token for preprocessor must come from an file source, as implies relative imports, this must never happen and should consider as an bug in toolchain."
    assert include_token.location.source == "file", msg
    assert include_token.location.filepath, msg

    include_path = try_resolve_and_find_real_include_path(
        requested_include_path,
        current_path=include_token.location.filepath,
        search_paths=state.include_search_paths,
    )
    if include_path is None:
        raise PreprocessorIncludeFileNotFoundError(
            include_token=include_token,
            include_path=requested_include_path,
        )

    if include_path not in state.already_included_paths:
        state.already_included_paths.append(include_path)
        io = open_source_file_line_stream(include_path)
        lexer = tokenize_from_raw(include_path, io)
        state.tokenizers.append(lexer)


def _consume_include_raw_path_from_token(
    include_token: Token,
    state: PreprocessorState,
) -> Path:
    """Consume include path from `include` construction."""
    assert include_token.type == TokenType.KEYWORD
    assert include_token.value == PreprocessorKeyword.INCLUDE

    include_path_token = next(state.tokenizer, None)
    if not include_path_token:
        raise PreprocessorIncludeNoPathError(include_token=include_token)
    if include_path_token.type != TokenType.STRING:
        raise PreprocessorIncludeNonStringNameError(
            include_path_token=include_path_token,
        )

    include_path_raw = include_path_token.value
    assert isinstance(include_path_raw, str)
    return Path(include_path_raw)
