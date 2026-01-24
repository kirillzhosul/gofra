"""Parser for function definitions in Gofra language.

Functions is an block like:
{inline|extern...} func function_name[signature_types,...] return_type

For example:
```
func my_func[] void ... end
inline func do_something[int, int] int ... end
extern func puts[*char[]] int
```

Extern functions cannot have a body so they do not have `end` block (assuming that - does not have any body block).
"""

from collections.abc import Generator
from dataclasses import dataclass

from libgofra.lexer import Token
from libgofra.lexer.keywords import KEYWORD_TO_NAME, WORD_TO_KEYWORD, Keyword
from libgofra.lexer.tokens import TokenType
from libgofra.parser._context import ParserContext
from libgofra.parser.type_parser import consume_function_signature
from libgofra.types import Type

from .exceptions import (
    ParserExpectedFunctionAfterFunctionModifiersError,
    ParserExpectedFunctionKeywordError,
    ParserFunctionInvalidTypeError,
    ParserFunctionIsBothInlineAndExternalError,
    ParserFunctionModifierReappliedError,
)

# TODO(@kirillzhosul): Refactor these ALL errors
_ = ParserFunctionInvalidTypeError


@dataclass
class FunctionHeaderQualifiers:
    is_inline: bool
    is_extern: bool
    is_public: bool
    is_no_return: bool


@dataclass
class FunctionHeaderDefinition:
    at: Token
    name: str
    parameters: list[tuple[str, Type]]
    return_type: Type

    qualifiers: FunctionHeaderQualifiers


def consume_function_definition(
    context: ParserContext,
    token: Token,
) -> FunctionHeaderDefinition:
    token, qualifiers = consume_function_qualifiers(context, token)
    function_name, parameters, return_type = consume_function_signature(context, token)

    return FunctionHeaderDefinition(
        token,
        function_name,
        parameters,
        return_type,
        qualifiers,
    )


def consume_function_qualifiers(
    context: ParserContext,
    token: Token,
) -> tuple[Token, FunctionHeaderQualifiers]:
    """Consume parser context assuming given token is last popped, and it is a function modifier (or base function).

    Accepts `inline`, `extern`, `function` keywords as tokens.
    Returns the last token (function name) and a tuple of flags (is_inline, is_extern).
    """
    # Function modifier parsing must be started from modifier or start
    assert token.type == TokenType.KEYWORD
    assert token.value in (
        Keyword.FUNCTION,
        Keyword.ATTR_FUNC_INLINE,
        Keyword.ATTR_FUNC_EXTERN,
        Keyword.ATTR_FUNC_PUBLIC,
        Keyword.ATTR_FUNC_NO_RETURN,
    )

    qualifiers = FunctionHeaderQualifiers(
        is_inline=False,
        is_extern=False,
        is_public=False,
        is_no_return=False,
    )

    next_token = token
    while next_token:
        if next_token.type != TokenType.KEYWORD:
            raise ParserExpectedFunctionKeywordError(token=next_token)

        match next_token.value:
            case Keyword.ATTR_FUNC_INLINE:
                if qualifiers.is_inline:
                    raise ParserFunctionModifierReappliedError(
                        modifier_token=next_token,
                    )
                qualifiers.is_inline = True
            case Keyword.ATTR_FUNC_EXTERN:
                if qualifiers.is_extern:
                    raise ParserFunctionModifierReappliedError(
                        modifier_token=next_token,
                    )
                qualifiers.is_extern = True
            case Keyword.FUNCTION:
                break
            case Keyword.ATTR_FUNC_PUBLIC:
                if qualifiers.is_public:
                    raise ParserFunctionModifierReappliedError(
                        modifier_token=next_token,
                    )
                qualifiers.is_public = True
            case Keyword.ATTR_FUNC_NO_RETURN:
                qualifiers.is_no_return = True
            case _:
                raise ParserExpectedFunctionKeywordError(token=next_token)

        if qualifiers.is_extern and qualifiers.is_inline:
            raise ParserFunctionIsBothInlineAndExternalError(
                modifier_token=next_token,
            )
        next_token = context.next_token()

    if next_token.type != TokenType.KEYWORD or next_token.value != Keyword.FUNCTION:
        raise ParserExpectedFunctionAfterFunctionModifiersError(modifier_token=token)

    return (next_token, qualifiers)


def consume_function_body_tokens(context: ParserContext) -> Generator[Token]:
    opened_context_blocks = 0

    context_keywords = (Keyword.IF, Keyword.DO)
    end_keyword_text = KEYWORD_TO_NAME[Keyword.END]

    while token := context.next_token():
        if token.type == TokenType.EOF:
            msg = f"Expected function to be closed but got end of file at {token.location}"
            raise ValueError(msg)
        if token.type != TokenType.KEYWORD:
            yield token
            continue

        if token.text == end_keyword_text:
            if opened_context_blocks <= 0:
                break
            opened_context_blocks -= 1

        is_context_keyword = WORD_TO_KEYWORD[token.text] in context_keywords
        if is_context_keyword:
            opened_context_blocks += 1

        yield token
