from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from gofra.lexer import Token
from gofra.lexer.keywords import PreprocessorKeyword
from gofra.lexer.tokens import TokenLocation, TokenType
from gofra.parser.intrinsics import WORD_TO_INTRINSIC

from .exceptions import (
    PreprocessorMacroContainsKeywordError,
    PreprocessorMacroNonWordNameError,
    PreprocessorMacroRedefinedError,
    PreprocessorMacroRedefinesLanguageWordError,
    PreprocessorNoMacroNameError,
)

if TYPE_CHECKING:
    from gofra.preprocessor._state import PreprocessorState

    from .macro import Macro

# Macros name can only be an word, but this does not adds additional validation
# that set contains word that considered as prohibited
PROHIBITED_MACRO_NAMES = WORD_TO_INTRINSIC.keys()


def consume_macro_definition_from_token(
    token: Token,
    state: PreprocessorState,
) -> Macro:
    """Consume macro definition block tokens into preprocessed macro container with validation."""
    assert token.type == TokenType.KEYWORD
    assert token.value == PreprocessorKeyword.DEFINE
    name = _consume_macro_name(token.location, state)

    macro = state.macros.new(token.location, name)
    _consume_macro_definition(macro, state)

    return macro


def try_resolve_and_expand_macro_reference_from_token(
    token: Token,
    state: PreprocessorState,
) -> bool:
    """Try to search for defined macro and resolve it with expansion if possible."""
    assert token.type == TokenType.WORD
    assert isinstance(token.value, str)

    name = token.value
    if not (macro := state.macros.get(name)):
        # Macro definition does not exists - do not expand
        return False

    tokenizer = iter(macro.tokens)
    state.tokenizers.append(tokenizer)

    return True


def _consume_macro_name(location: TokenLocation, state: PreprocessorState) -> str:
    """Consume and validate macro name from beginning of an macro definition."""
    if not (token := next(state.tokenizer, None)):
        raise PreprocessorNoMacroNameError(location=location)

    if token.type != TokenType.WORD:
        raise PreprocessorMacroNonWordNameError(token=token)

    name = token.text
    if original := state.macros.get(name):
        raise PreprocessorMacroRedefinedError(
            name=name,
            redefined=token.location,
            original=original.location,
        )

    if name in PROHIBITED_MACRO_NAMES:
        raise PreprocessorMacroRedefinesLanguageWordError(
            location=token.location,
            name=name,
        )
    return name


def _consume_macro_definition(
    macro: Macro,
    state: PreprocessorState,
) -> None:
    """Consume current tokenizer state into macro block container tokens."""
    while token := next(state.tokenizer, None):
        if token.type == TokenType.EOL:
            # Macro deifinition is line-dependant so it consumes until first end-of-line (EOL)
            break

        if token.type == TokenType.KEYWORD:
            raise PreprocessorMacroContainsKeywordError(macro=macro, keyword=token)

        # Ensure that there is no lexer level new token types.
        if token.type not in (
            TokenType.INTEGER,
            TokenType.CHARACTER,
            TokenType.STRING,
            TokenType.WORD,
        ):
            assert_never(token.type)

        macro.tokens.append(token)
        continue

    if not macro.tokens:
        # We encoutered an empty macro, which must contain default token `1` (preprocessor conditions default)
        default = 1
        token = Token(
            type=TokenType.INTEGER,
            text=str(default),
            value=default,
            location=macro.location,
        )
        macro.tokens.append(token)
