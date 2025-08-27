from __future__ import annotations

from typing import TYPE_CHECKING

from gofra.lexer.keywords import Keyword
from gofra.lexer.tokens import Token, TokenType

from .exceptions import (
    PreprocessorConditionalConsumeUntilEndifContextSwitchError,
    PreprocessorConditionalNoMacroNameError,
)

if TYPE_CHECKING:
    from gofra.preprocessor._state import PreprocessorState
    from gofra.preprocessor.macros.container import Macro


def resolve_conditional_block_from_token(
    token: Token,
    state: PreprocessorState,
) -> None:
    macro = _consume_macro_from_token(token, state)
    match token:
        case Token(type=TokenType.KEYWORD, value=Keyword.PP_IFDEF):
            if not macro:
                _consume_until_endif(token, state)
        case _:
            msg = "Expected resolve conditional block to receive an known preprocessor keyword token"
            raise AssertionError(msg)


def _consume_until_endif(from_token: Token, state: PreprocessorState) -> None:
    while token := next(state.tokenizer, None):
        if token.type != TokenType.KEYWORD:
            continue
        if token.value == Keyword.PP_ENDIF:
            return
        if token.location.filepath != from_token.location.filepath:
            raise PreprocessorConditionalConsumeUntilEndifContextSwitchError(
                conditional_token=from_token,
            )


def _consume_macro_from_token(token: Token, state: PreprocessorState) -> Macro | None:
    macro_name = next(state.tokenizer, None)
    if not macro_name:
        raise PreprocessorConditionalNoMacroNameError(conditional_token=token)
    if macro_name.type != TokenType.WORD:
        raise ValueError
    assert isinstance(macro_name.value, str)
    return state.macros.get(macro_name.value)
