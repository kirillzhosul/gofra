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

from gofra.lexer import Token
from gofra.lexer.keywords import KEYWORD_TO_NAME, WORD_TO_KEYWORD, Keyword
from gofra.lexer.tokens import TokenType
from gofra.parser._context import ParserContext
from gofra.parser.types import parse_type_from_text, parser_type_from_tokenizer
from gofra.types import Type, VoidType

from .exceptions import (
    ParserExpectedFunctionAfterFunctionModifiersError,
    ParserExpectedFunctionKeywordError,
    ParserFunctionInvalidTypeError,
    ParserFunctionIsBothInlineAndExternalError,
    ParserFunctionModifierReappliedError,
    ParserFunctionNoNameError,
)

# TODO(@kirillzhosul): Refactor these ALL errors
_ = ParserFunctionInvalidTypeError


def consume_function_definition(
    context: ParserContext,
    token: Token,
) -> tuple[Token, str, list[Type], Type, bool, bool, bool]:
    token, (qualifier_is_inline, qualifier_is_extern, qualifier_is_global) = (
        consume_function_qualifiers(
            context,
            token,
        )
    )
    function_name, parameters, return_type = consume_function_signature(context, token)

    return (
        token,
        function_name,
        parameters,
        return_type,
        qualifier_is_inline,
        qualifier_is_extern,
        qualifier_is_global,
    )


def consume_function_qualifiers(
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

    qualifier_is_extern = False
    qualifier_is_inline = False
    qualifier_is_global = False

    next_token = token
    while next_token:
        if next_token.type != TokenType.KEYWORD:
            raise ParserExpectedFunctionKeywordError(token=next_token)

        match next_token.value:
            case Keyword.INLINE:
                if qualifier_is_inline:
                    raise ParserFunctionModifierReappliedError(
                        modifier_token=next_token,
                    )
                qualifier_is_inline = True
            case Keyword.EXTERN:
                if qualifier_is_extern:
                    raise ParserFunctionModifierReappliedError(
                        modifier_token=next_token,
                    )
                qualifier_is_extern = True
            case Keyword.FUNCTION:
                break
            case Keyword.GLOBAL:
                if qualifier_is_global:
                    raise ParserFunctionModifierReappliedError(
                        modifier_token=next_token,
                    )
                qualifier_is_global = True
            case _:
                raise ParserExpectedFunctionKeywordError(token=next_token)

        if qualifier_is_extern and qualifier_is_inline:
            raise ParserFunctionIsBothInlineAndExternalError(
                modifier_token=next_token,
            )
        next_token = context.next_token()

    if next_token.type != TokenType.KEYWORD or next_token.value != Keyword.FUNCTION:
        raise ParserExpectedFunctionAfterFunctionModifiersError(modifier_token=token)

    return next_token, (qualifier_is_inline, qualifier_is_extern, qualifier_is_global)


def consume_function_signature(
    context: ParserContext,
    token: Token,
) -> tuple[str, list[Type], Type]:
    """Consume parser context into function signature assuming given token is `function` keyword.

    Returns function name and signature types (`in` and `out).
    """
    type_contract_out = parser_type_from_tokenizer(context)

    name_token = context.next_token()

    if not name_token:
        raise ParserFunctionNoNameError(token=token)
    if name_token.type != TokenType.IDENTIFIER:
        msg = f"Expected function name in signature but got {name_token.type.name} at {name_token.location}"
        raise ValueError(msg)
    function_name = name_token.text
    parameters = consume_function_parameters(context)

    return function_name, parameters, type_contract_out


def consume_function_parameters(context: ParserContext) -> list[Type]:
    parameters: list[Type] = []

    paren_token = context.next_token()
    if paren_token.type != TokenType.LBRACKET:
        msg = f"Expected LBRACKET `[` after function name for parameters but got {paren_token.type.name}"
        raise ValueError(msg, paren_token.location)

    # TODO(@kirillzhosul): allows trailing comma after last typename
    typename_tokens: list[list[Token]] = [[]]

    unbalanced_brackets = 0
    while token := context.next_token():
        if token.type == TokenType.EOL:
            continue

        if token.type == TokenType.COMMA:
            if not typename_tokens:
                msg = "expected typename for parameter before comma separator"
                raise ValueError(msg)
            typename_tokens.append([])
            continue

        if token.type == TokenType.LBRACKET:
            unbalanced_brackets += 1

        if token.type == TokenType.RBRACKET:
            if unbalanced_brackets == 0:
                break
            unbalanced_brackets -= 1

        if token.type == TokenType.EOF:
            msg = "Expected RBRACKET `]` after function parameters but got end of file!"
            raise ValueError(msg)

        if token.type not in (
            TokenType.IDENTIFIER,
            TokenType.INTEGER,
            TokenType.RBRACKET,
            TokenType.LBRACKET,
            TokenType.STAR,
        ):
            msg = f"Expected only identifiers or typename allowed tokens in function parameters but got {token.type.name} at {token.location}"
            raise ValueError(msg)

        # Buffering type name tokens for parsing at comma separator
        typename_tokens[-1].append(token)

    # TODO(@kirillzhosul): refactor into parse_type_from_tokenizer
    for t_tokens in typename_tokens:
        if not t_tokens:
            if len(typename_tokens) == 1:
                # empty parameters
                break
            msg = "expected typename after token"
            raise ValueError(msg, token.location)
        typename_text = "".join(t.text for t in t_tokens)
        parameter_type = parse_type_from_text(context, typename_text)
        if not parameter_type:
            msg = f"unknown parameter type {typename_text}"
            raise ValueError(msg)

        if isinstance(parameter_type, VoidType):
            # TODO(@kirillzhosul): Consider an warning
            pass
        else:
            parameters.append(parameter_type)

    return parameters


def consume_function_body_tokens(context: ParserContext) -> Generator[Token]:
    opened_context_blocks = 0

    context_keywords = (Keyword.IF, Keyword.DO)
    end_keyword_text = KEYWORD_TO_NAME[Keyword.END]

    while token := context.next_token():
        if token.type == TokenType.EOF:
            msg = "Expected function to be closed but got end of file"
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
