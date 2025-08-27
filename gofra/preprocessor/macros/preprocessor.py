from __future__ import annotations

from typing import TYPE_CHECKING

from gofra.lexer.keywords import WORD_TO_KEYWORD, Keyword
from gofra.lexer.tokens import TokenType
from gofra.parser.intrinsics import WORD_TO_INTRINSIC

from .container import Macro
from .exceptions import (
    PreprocessorMacroDefinesMacroError,
    PreprocessorMacroNonWordNameError,
    PreprocessorMacroRedefinedError,
    PreprocessorMacroRedefinesLanguageDefinitionError,
    PreprocessorNoMacroNameError,
    PreprocessorUnclosedMacroError,
)

if TYPE_CHECKING:
    from gofra.lexer import Token
    from gofra.preprocessor._state import PreprocessorState

PROHIBITED_MACRO_NAMES = WORD_TO_INTRINSIC.keys() | WORD_TO_KEYWORD.keys()


def define_macro_block_from_token(token: Token, state: PreprocessorState) -> None:
    macro_name = _consume_macro_name_from_token(token, state)
    macro = _define_empty_macro(state, token, macro_name)
    _consume_tokenizer_from_state_into_macro(macro, state)


def try_resolve_macro_reference_from_token(
    token: Token,
    state: PreprocessorState,
) -> bool:
    """Try to search for defined macro and resolve it if possible."""
    assert token.type == TokenType.WORD
    assert isinstance(token.value, str)

    macro = state.macros.get(token.value)
    if not macro:
        return False

    state.tokenizers.append(macro.as_tokenizer())
    return True


def _consume_macro_name_from_token(token: Token, state: PreprocessorState) -> str:
    """Consume macro name from `macro` construction."""
    macro_name_token = next(state.tokenizer, None)
    if not macro_name_token:
        raise PreprocessorNoMacroNameError(macro_token=token)
    if macro_name_token.type != TokenType.WORD:
        raise PreprocessorMacroNonWordNameError(macro_name_token=macro_name_token)

    macro_name = macro_name_token.text
    if macro_name in state.macros:
        raise PreprocessorMacroRedefinedError(
            redefine_macro_name_token=macro_name_token,
            original_macro_location=state.macros[macro_name].token.location,
        )
    if macro_name in PROHIBITED_MACRO_NAMES:
        raise PreprocessorMacroRedefinesLanguageDefinitionError(
            macro_token=macro_name_token,
            macro_name=macro_name,
        )
    return macro_name


def _define_empty_macro(
    state: PreprocessorState,
    token: Token,
    name: str,
) -> Macro:
    """Create empty macro that start at given token to fill it preprocessed tokens."""
    macro = Macro(token=token, tokens=[], name=name)
    state.macros[name] = macro
    return macro


def _consume_tokenizer_from_state_into_macro(
    macro: Macro,
    state: PreprocessorState,
) -> None:
    """Consume current tokenizer into macro block."""
    opened_context_blocks = 0
    macro_was_closed = False

    while token := next(state.tokenizer, None):
        if token.type == TokenType.KEYWORD:
            if token.value == Keyword.PP_MACRO:
                raise PreprocessorMacroDefinesMacroError(
                    macro_token=macro.token,
                    macro_name=macro.name,
                )
            if token.value == Keyword.END:
                if opened_context_blocks <= 0:
                    macro_was_closed = True
                    break
                opened_context_blocks -= 1
            if token.value in (Keyword.IF, Keyword.DO, Keyword.FUNCTION):
                opened_context_blocks += 1
        macro.tokens.append(token)
    if not macro_was_closed:
        raise PreprocessorUnclosedMacroError(
            macro_token=macro.token,
            macro_name=macro.name,
        )
