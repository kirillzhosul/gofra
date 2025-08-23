"""Parser for function definitions in Gofra language.

Functions is an block like:
{inline|extern...} func function_name[signature_types,...] return_type

For example:
```
func my_func[] void ... end
inline func do_something[int, int] int ... end
extern func puts[ptr] int
```

Extern functions cannot have a body so they do not have `end` block (assuming that - does not have any body block).
"""

from gofra.lexer import Token
from gofra.lexer.keywords import Keyword
from gofra.lexer.tokens import TokenType
from gofra.parser._context import ParserContext
from gofra.typecheck.types import WORD_TO_GOFRA_TYPE, GofraType

from .exceptions import (
    ParserExpectedFunctionAfterFunctionModifiersError,
    ParserExpectedFunctionKeywordError,
    ParserExpectedFunctionReturnTypeError,
    ParserFunctionInvalidTypeError,
    ParserFunctionIsBothInlineAndExternalError,
    ParserFunctionModifierReappliedError,
    ParserFunctionNoNameError,
)


def consume_function_definition(
    context: ParserContext,
    token: Token,
) -> tuple[Token, str, list[GofraType], list[GofraType], bool, bool, bool]:
    token, (modifier_is_inline, modifier_is_extern, modifier_is_global) = (
        consume_function_modifiers(
            context,
            token,
        )
    )
    function_name, type_contract_in, type_contract_out = consume_function_signature(
        context,
        token,
    )

    return (
        token,
        function_name,
        type_contract_in,
        type_contract_out,
        modifier_is_inline,
        modifier_is_extern,
        modifier_is_global,
    )


def consume_function_modifiers(
    context: ParserContext,
    token: Token,
) -> tuple[Token, tuple[bool, bool, bool]]:
    """Consume parser context assuming given token is last popped, and it is a function modifier (or base function).

    Accepts `inline`, `extern`, `function` keywords as tokens.
    Returns the last token (function name) and a tuple of flags (is_inline, is_extern).
    """
    # Function modifier parsing must be started from modifier or start
    assert token.type == TokenType.KEYWORD
    assert token.value in (
        Keyword.INLINE,
        Keyword.EXTERN,
        Keyword.FUNCTION,
        Keyword.GLOBAL,
    )

    mark_is_extern = False
    mark_is_inline = False
    mark_is_global = False

    next_token = token
    while next_token:
        if next_token.type != TokenType.KEYWORD:
            raise ParserExpectedFunctionKeywordError(token=next_token)

        match next_token.value:
            case Keyword.INLINE:
                if mark_is_inline:
                    raise ParserFunctionModifierReappliedError(
                        modifier_token=next_token,
                    )
                mark_is_inline = True
            case Keyword.EXTERN:
                if mark_is_extern:
                    raise ParserFunctionModifierReappliedError(
                        modifier_token=next_token,
                    )
                mark_is_extern = True
            case Keyword.FUNCTION:
                break
            case Keyword.GLOBAL:
                if mark_is_global:
                    raise ParserFunctionModifierReappliedError(
                        modifier_token=next_token,
                    )
                mark_is_global = True
            case _:
                raise ParserExpectedFunctionKeywordError(token=next_token)

        if mark_is_extern and mark_is_inline:
            raise ParserFunctionIsBothInlineAndExternalError(
                modifier_token=next_token,
            )
        next_token = next(context.tokenizer, None)

    if not next_token:
        raise NotImplementedError
    if next_token.type != TokenType.KEYWORD or next_token.value != Keyword.FUNCTION:
        raise ParserExpectedFunctionAfterFunctionModifiersError(modifier_token=token)

    return next_token, (mark_is_inline, mark_is_extern, mark_is_global)


def consume_function_signature(
    context: ParserContext,
    token: Token,
) -> tuple[str, list[GofraType], list[GofraType]]:
    """Consume parser context into function signature assuming given token is `function` keyword.

    Returns function name and signature types (`in` and `out).
    """

    sig_token = next(context.tokenizer, None)
    if not sig_token:
        raise ParserExpectedFunctionReturnTypeError(
            definition_token=token,
        )
    if sig_token.type != TokenType.WORD:
        raise ValueError

    type_contract_out = _parse_function_type_contract(
        token=sig_token,
        contract=(
            sig_token.text
            if sig_token.text.startswith("[") and sig_token.text.endswith("]")
            else f"[{sig_token.text}]"
        ),
    )

    signature_token = next(context.tokenizer, None)
    if not signature_token:
        raise ParserFunctionNoNameError(token=token)

    signature = signature_token.text

    # Assume for the first time that function has no input contract
    function_name = signature
    type_contract_in = []

    if "[" in signature and "]" in signature:
        function_name = function_name.split("[")[0].strip()
        contract = signature.split("[")[1].strip()[:-1]

        type_contract_in = _parse_function_type_contract(
            token=signature_token,
            contract=f"[{contract}]",
        )

    return function_name, type_contract_in, type_contract_out


def _parse_function_type_contract(token: Token, contract: str) -> list[GofraType]:
    """Parse function type contract from string.

    Expected contract to be like: `[ptr,int,int]`
    """
    assert contract.startswith("[")
    assert contract.endswith("]")

    raw_contract_types = [t.strip() for t in contract[1:-1].split(",") if t != ""]

    for raw_contract_type in raw_contract_types:
        if raw_contract_type not in WORD_TO_GOFRA_TYPE:
            raise ParserFunctionInvalidTypeError(
                type_token=token,
                requested_type=raw_contract_type,
            )

    return [
        WORD_TO_GOFRA_TYPE[raw_contract_type]
        for raw_contract_type in raw_contract_types
        if raw_contract_type != ""
        and WORD_TO_GOFRA_TYPE[raw_contract_type] != GofraType.VOID
    ]


"""
def _consume_function_definition_name_with_types(
    context: ParserContext,
    token: Token,
) -> tuple[GofraType, str, list[GofraType]]:


    if function_name in context.macros:
        macro_reference = context.macros[function_name]
        raise ParserExternRedefinesMacroError(
            redefine_extern_function_name_token=function_sig_def_token,
            original_macro_name=macro_reference.name,
            original_macro_location=macro_reference.location,
        )

    if function_name in (WORD_TO_INTRINSIC.keys() | WORD_TO_KEYWORD.keys()):
        raise ParserExternRedefinesLanguageDefinitionError(
            extern_token=function_sig_def_token,
            extern_function_name=function_name,
        )

    return return_type, function_name, signature_types
"""
