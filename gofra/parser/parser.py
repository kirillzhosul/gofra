from __future__ import annotations

from difflib import get_close_matches
from typing import TYPE_CHECKING, assert_never

from gofra.consts import GOFRA_ENTRY_POINT
from gofra.hir.function import Function
from gofra.hir.module import Module
from gofra.lexer import (
    Keyword,
    Token,
    TokenType,
)
from gofra.lexer.keywords import PreprocessorKeyword
from gofra.parser.conditional_blocks import consume_conditional_block_keyword_from_token
from gofra.parser.functions.parser import (
    consume_function_body_tokens,
    consume_function_definition,
)
from gofra.parser.structures import unpack_structure_definition_from_token
from gofra.parser.typecast import unpack_typecast_from_token
from gofra.parser.variables import (
    get_all_scopes_variables,
    try_push_variable_reference,
    unpack_variable_definition_from_token,
)

from ._context import ParserContext
from .exceptions import (
    ParserDirtyNonPreprocessedTokenError,
    ParserExhaustiveContextStackError,
    ParserUnfinishedIfBlockError,
    ParserUnfinishedWhileDoBlockError,
    ParserUnknownFunctionError,
    ParserUnknownIdentifierError,
)
from .operators import IDENTIFIER_TO_OPERATOR_TYPE, OperatorType

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


def parse_module_from_tokenizer(path: Path, tokenizer: Generator[Token]) -> Module:
    """Load file for parsing into operators."""
    context = ParserContext(_tokenizer=tokenizer)
    _parse_from_context_into_operators(context=context)

    assert context.is_top_level, (
        "Parser context in result of parsing must an top level, bug in a parser"
    )
    assert not context.operators, (
        f"Expected NO operators on top level, first one is at {context.operators[0].location}"
    )

    return Module(
        path=path,
        functions=context.functions,
        variables=context.variables,
        structures=context.structs,
    )


def _parse_from_context_into_operators(context: ParserContext) -> None:
    """Consumes token stream into language operators."""
    try:
        while token := context.next_token():
            _consume_token_for_parsing(
                token=token,
                context=context,
            )
    except StopIteration:
        pass

    if context.context_stack:
        _, unclosed_operator = context.pop_context_stack()
        match unclosed_operator.type:
            case OperatorType.CONDITIONAL_DO | OperatorType.CONDITIONAL_WHILE:
                raise ParserUnfinishedWhileDoBlockError(token=unclosed_operator.token)
            case OperatorType.CONDITIONAL_IF:
                raise ParserUnfinishedIfBlockError(if_token=unclosed_operator.token)
            case _:
                raise ParserExhaustiveContextStackError


def _consume_token_for_parsing(token: Token, context: ParserContext) -> None:
    match token.type:
        case TokenType.INTEGER | TokenType.CHARACTER:
            return _push_integer_operator(context, token)
        case TokenType.STRING:
            return _push_string_operator(context, token)
        case TokenType.IDENTIFIER:
            return _consume_word_token(token, context)
        case TokenType.KEYWORD:
            return _consume_keyword_token(context, token)
        case TokenType.EOL | TokenType.EOF:
            return None
        case TokenType.STAR:
            if context.is_top_level:
                msg = "expected STAR with meaning of multiply intrinsic to be at top level."
                raise ValueError(msg)
            context.push_new_operator(OperatorType.ARITHMETIC_MULTIPLY, token=token)
            return None
        case (
            TokenType.LBRACKET
            | TokenType.RBRACKET
            | TokenType.LPAREN
            | TokenType.RPAREN
            | TokenType.DOT
            | TokenType.COMMA
            | TokenType.SEMICOLON
            | TokenType.COLON
            | TokenType.RCURLY
            | TokenType.LCURLY
        ):
            msg = f"Got {token.type.name} ({token.location}) in form of an single parser-expression (non-composite). This token (as other symbol-defined ones) must occur only in composite expressions (e.g function signature, type constructions)."
            raise ValueError(msg)


def _consume_word_token(token: Token, context: ParserContext) -> None:
    if _try_unpack_function_call_from_identifier_token(context, token):
        return

    if _try_push_intrinsic_operator(context, token):
        return

    if try_push_variable_reference(context, token):
        return

    names_available = context.functions.keys() | [
        v.name for v in get_all_scopes_variables(context)
    ]
    raise ParserUnknownIdentifierError(
        word_token=token,
        names_available=names_available,
        best_match=_best_match_for_word(context, token.text),
    )


def _best_match_for_word(context: ParserContext, word: str) -> str | None:
    matches = get_close_matches(
        word,
        IDENTIFIER_TO_OPERATOR_TYPE.keys()
        | context.functions.keys()
        | context.variables.keys(),
    )
    return matches[0] if matches else None


def _consume_keyword_token(context: ParserContext, token: Token) -> None:
    if isinstance(token.value, PreprocessorKeyword):
        raise ParserDirtyNonPreprocessedTokenError(token=token)
    assert isinstance(token.value, Keyword)

    TOP_LEVEL_KEYWORD = (  # noqa: N806
        Keyword.INLINE,
        Keyword.EXTERN,
        Keyword.FUNCTION,
        Keyword.GLOBAL,
        Keyword.STRUCT,
    )

    BOTH_LEVEL_KEYWORD = (  # noqa: N806
        Keyword.END,
        Keyword.VARIABLE_DEFINE,
    )
    if context.is_top_level:
        if token.value not in (*TOP_LEVEL_KEYWORD, *BOTH_LEVEL_KEYWORD):
            msg = f"{token.value.name} expected to be in functions scope not at global scope!"
            raise ValueError(msg)
    elif token.value in TOP_LEVEL_KEYWORD:
        msg = f"{token.value.name} expected to be only inside global scope!"
        raise ValueError(msg, token.location)

    match token.value:
        case Keyword.IF | Keyword.DO | Keyword.WHILE | Keyword.END:
            return consume_conditional_block_keyword_from_token(context, token)
        case Keyword.INLINE | Keyword.EXTERN | Keyword.FUNCTION | Keyword.GLOBAL:
            return _unpack_function_definition_from_token(context, token)
        case Keyword.FUNCTION_CALL:
            return _unpack_function_call_from_token(context, token)
        case Keyword.FUNCTION_RETURN:
            return context.push_new_operator(OperatorType.FUNCTION_RETURN, token=token)
        case Keyword.TYPE_CAST:
            return unpack_typecast_from_token(context, token)
        case Keyword.VARIABLE_DEFINE:
            return unpack_variable_definition_from_token(context)
        case Keyword.SYSCALL:
            return context.push_new_operator(
                type=OperatorType.SYSCALL,
                token=token,
                operand=int(token.text[-1]),
            )
        case Keyword.STRUCT:
            return unpack_structure_definition_from_token(context)
        case Keyword.DEBUGGER_BREAKPOINT | Keyword.COPY | Keyword.DROP | Keyword.SWAP:
            return context.push_new_operator(
                type={
                    Keyword.DEBUGGER_BREAKPOINT: OperatorType.DEBUGGER_BREAKPOINT,
                    Keyword.COPY: OperatorType.STACK_COPY,
                    Keyword.DROP: OperatorType.STACK_DROP,
                    Keyword.SWAP: OperatorType.STACK_SWAP,
                }[token.value],
                token=token,
            )
        case _:
            assert_never(token.value)


def _unpack_function_call_from_token(context: ParserContext, token: Token) -> None:
    name_token = context.next_token()
    if name_token.type != TokenType.IDENTIFIER:
        msg = "expected function name as identifier after `call`"
        raise ValueError(msg)

    name = name_token.text
    function = context.functions.get(name)

    if not function:
        raise ParserUnknownFunctionError(
            token=name_token,
            functions_available=context.functions.keys(),
            best_match=_best_match_for_word(context, token.text),
        )

    if function.is_inline:
        assert not function.is_external
        context.expand_from_inline_block(function)
        return

    context.push_new_operator(
        OperatorType.FUNCTION_CALL,
        token=token,
        operand=function.name,
    )


def _unpack_function_definition_from_token(
    context: ParserContext,
    token: Token,
) -> None:
    (
        token,
        function_name,
        parameters,
        return_type,
        modifier_is_inline,
        modifier_is_extern,
        modifier_is_global,
    ) = consume_function_definition(context, token)

    if modifier_is_extern:
        function = Function.create_external(
            name=function_name,
            defined_at=token.location,
            parameters=parameters,
            return_type=return_type,
        )
        context.add_function(function)
        return

    if context.name_is_already_taken(function_name):
        msg = f"Function name {function_name} is already taken by other definition"
        raise ValueError(msg)

    new_context = ParserContext(
        _tokenizer=consume_function_body_tokens(context),
        functions=context.functions,
        parent=context,
    )

    _parse_from_context_into_operators(context=new_context)
    if modifier_is_inline:
        assert not new_context.variables, "Inline functions cannot have local variables"
        function = Function.create_internal_inline(
            name=function_name,
            defined_at=token.location,
            operators=new_context.operators,
            return_type=return_type,
            parameters=parameters,
        )
        context.add_function(function)
        return
    if function_name == GOFRA_ENTRY_POINT:
        modifier_is_global = True

    function = Function.create_internal(
        name=function_name,
        defined_at=token.location,
        operators=new_context.operators,
        variables=new_context.variables,
        parameters=parameters,
        return_type=return_type,
        is_global=modifier_is_global,
        is_leaf=new_context.is_leaf_context,
    )
    context.add_function(function)


def _try_unpack_function_call_from_identifier_token(
    context: ParserContext,
    token: Token,
) -> bool:
    assert token.type == TokenType.IDENTIFIER

    function = context.functions.get(token.text, None)
    if function:
        if function.is_inline:
            context.expand_from_inline_block(function)
            return True
        context.push_new_operator(
            type=OperatorType.FUNCTION_CALL,
            token=token,
            operand=function.name,
        )
        return True

    return False


def _push_string_operator(context: ParserContext, token: Token) -> None:
    assert isinstance(token.value, str)
    context.push_new_operator(
        type=OperatorType.PUSH_STRING,
        token=token,
        operand=token.value,
    )


def _push_integer_operator(context: ParserContext, token: Token) -> None:
    assert isinstance(token.value, int)
    context.push_new_operator(
        type=OperatorType.PUSH_INTEGER,
        token=token,
        operand=token.value,
    )


def _try_push_intrinsic_operator(context: ParserContext, token: Token) -> bool:
    assert isinstance(token.value, str)

    operator_type = IDENTIFIER_TO_OPERATOR_TYPE.get(token.value)
    if operator_type:
        context.push_new_operator(type=operator_type, token=token)
        return True

    return False
