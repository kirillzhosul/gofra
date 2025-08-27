from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from gofra.lexer.keywords import Keyword
from gofra.lexer.lexer import tokenize_file
from gofra.lexer.tokens import Token, TokenType

from .exceptions import (
    PreprocessorIncludeCurrentFileError,
    PreprocessorIncludeFileNotFoundError,
    PreprocessorIncludeNonStringNameError,
    PreprocessorIncludeNoPathError,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from gofra.preprocessor._state import PreprocessorState


def resolve_include_from_token_into_state(
    include_token: Token,
    state: PreprocessorState,
) -> None:
    """Consume and resolve include construction into real include at preprocessor side, ommiting include if already included."""
    requested_include_path = _consume_include_raw_path_from_token(include_token, state)
    if requested_include_path.resolve(strict=False) == state.path:
        raise PreprocessorIncludeCurrentFileError(include_path_token=include_token)

    include_path = _try_resolve_and_find_real_include_path(
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
        state.tokenizers.append(tokenize_file(include_path))


def _consume_include_raw_path_from_token(
    include_token: Token,
    state: PreprocessorState,
) -> Path:
    """Consume include path from `include` construction."""
    assert include_token.type == TokenType.KEYWORD
    assert include_token.value == Keyword.PP_INCLUDE

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


def _try_resolve_and_find_real_include_path(
    path: Path,
    current_path: Path,
    search_paths: Iterable[Path],
) -> Path | None:
    """Resolve real import path and try to search for possible location of include (include directories system)."""
    for search_path in (Path("./"), current_path.parent, *search_paths):
        if (probable_path := search_path.joinpath(path)).exists(follow_symlinks=True):
            if probable_path.is_file():
                # We found an straighforward file reference
                return probable_path

            # Non-existant file here or directory reference.
            if not probable_path.is_dir():
                continue

            probable_package = Path(probable_path / probable_path.name).with_suffix(
                ".gof",
            )
            if probable_package.exists():
                return probable_package
    return None
