from __future__ import annotations

from collections import OrderedDict
from difflib import get_close_matches
from typing import TYPE_CHECKING, assert_never

from gofra.feature_flags import FEATURE_DEREFERENCE_VARIABLES_BY_DEFAULT
from gofra.lexer import (
    Keyword,
    Token,
    TokenType,
)
from gofra.lexer.keywords import KEYWORD_TO_NAME, WORD_TO_KEYWORD, PreprocessorKeyword
from gofra.parser.conditional_blocks import consume_conditional_block_keyword_from_token
from gofra.parser.functions import Function
from gofra.parser.functions.parser import consume_function_definition
from gofra.parser.typecast import unpack_typecast_from_token
from gofra.parser.types import parser_type_from_tokenizer
from gofra.parser.validator import validate_and_pop_entry_point
from gofra.parser.variables import (
    Variable,
    get_all_scopes_variables,
    search_variable_in_context_parents,
)
from gofra.types.composite.array import ArrayType

from ._context import ParserContext
from .exceptions import (
    ParserDirtyNonPreprocessedTokenError,
    ParserExhaustiveContextStackError,
    ParserUnfinishedIfBlockError,
    ParserUnfinishedWhileDoBlockError,
    ParserUnknownFunctionError,
    ParserUnknownIdentifierError,
    ParserVariableNameAlreadyDefinedAsVariableError,
)
from .intrinsics import WORD_TO_INTRINSIC, Intrinsic
from .operators import OperatorType

if TYPE_CHECKING:
    from collections.abc import Generator


def wrapped_tokenizer(
    tokenizer: Generator[Token, None, None],
) -> Generator[Token, Token | None]:
    token_buffer: list[Token] = []

    for token in tokenizer:
        # Yield buffered tokens first
        while token_buffer:
            received = yield token_buffer.pop(0)
            if received is not None:
                token_buffer.append(received)

        # Yield from original tokenizer
        received = yield token
        if received is not None:
            token_buffer.append(received)

    # Yield any remaining buffered tokens
    while token_buffer:
        received = yield token_buffer.pop(0)
        if received is not None:
            token_buffer.append(received)


def parse_file(tokenizer: Generator[Token]) -> tuple[ParserContext, Function]:
    """Load file for parsing into operators."""
    context = _parse_from_context_into_operators(
        context=ParserContext(
            parent=None,
            _tokenizer=wrapped_tokenizer(tokenizer),
            functions={},
        ),
    )

    assert context.is_top_level, (
        "Parser context in result of parsing must an top level, bug in a parser"
    )
    assert not context.operators, (
        f"Expected NO operators on top level, first one is at {context.operators[0].token.location}"
    )

    entry_point = validate_and_pop_entry_point(context)
    return context, entry_point


def _parse_from_context_into_operators(context: ParserContext) -> ParserContext:
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
            case OperatorType.DO | OperatorType.WHILE:
                raise ParserUnfinishedWhileDoBlockError(token=unclosed_operator.token)
            case OperatorType.IF:
                raise ParserUnfinishedIfBlockError(if_token=unclosed_operator.token)
            case _:
                raise ParserExhaustiveContextStackError

    return context


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
            context.push_new_operator(
                OperatorType.INTRINSIC,
                token=token,
                operand=Intrinsic.MULTIPLY,
                is_contextual=False,
            )
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
    if _try_unpack_function_from_token(context, token):
        return

    if _try_push_intrinsic_operator(context, token):
        return

    if _try_push_variable_reference(context, token):
        return

    names_available = context.functions.keys() | [
        v.name for v in get_all_scopes_variables(context)
    ]
    raise ParserUnknownIdentifierError(
        word_token=token,
        names_available=names_available,
        best_match=_best_match_for_word(context, token.text),
    )


def _try_push_variable_reference(context: ParserContext, token: Token) -> bool:
    assert token.type == TokenType.IDENTIFIER

    varname = token.text

    is_reference = not FEATURE_DEREFERENCE_VARIABLES_BY_DEFAULT
    array_index_at = None

    if varname.startswith("&"):
        is_reference = True
        varname = varname.removeprefix("&")

    if context.peek_token().type == TokenType.LBRACKET:
        _ = context.next_token()  # Consume LBRACKET

        elements_token = context.next_token()
        if elements_token.type != TokenType.INTEGER:
            msg = (
                f"Expected array index inside of [], but got {elements_token.type.name}"
            )
            raise ValueError(msg)

        rbracket = context.next_token()
        if rbracket.type != TokenType.RBRACKET:
            msg = f"Expected RBRACKET after array index element qualifier but got {rbracket.type.name}"
            raise ValueError(msg)

        assert isinstance(elements_token.value, int)
        array_index_at = elements_token.value

    variable = search_variable_in_context_parents(context, varname)
    if not variable:
        return False

    context.push_new_operator(
        type=OperatorType.PUSH_MEMORY_POINTER,
        token=token,
        operand=(varname, variable.type),
        is_contextual=False,
    )

    if array_index_at is not None:
        if not isinstance(variable.type, ArrayType):
            msg = "cannot get index-of (e.g []) for non-array types."
            raise ValueError(msg)

        if array_index_at < 0:
            msg = "Negative indexing inside arrays is prohibited"
            raise ValueError(msg)

        if array_index_at >= variable.type.elements_count:
            msg = f"OOB (out-of-bounds) for array access `{token.text}` at {token.location}, array has {variable.type.elements_count} elements"
            raise ValueError(msg)

        element_sizeof = variable.type.element_type.size_in_bytes
        shift_in_bytes = element_sizeof * array_index_at
        if shift_in_bytes:
            context.push_new_operator(
                type=OperatorType.PUSH_INTEGER,
                token=token,
                operand=shift_in_bytes,
                is_contextual=False,
            )
            context.push_new_operator(
                type=OperatorType.INTRINSIC,
                token=token,
                operand=Intrinsic.PLUS,
                is_contextual=False,
            )

    if not is_reference:
        context.push_new_operator(
            type=OperatorType.INTRINSIC,
            token=token,
            operand=Intrinsic.MEMORY_LOAD,
            is_contextual=False,
        )
    return True


def _best_match_for_word(context: ParserContext, word: str) -> str | None:
    matches = get_close_matches(
        word,
        WORD_TO_INTRINSIC.keys() | context.functions.keys() | context.variables.keys(),
    )
    return matches[0] if matches else None


def _consume_keyword_token(context: ParserContext, token: Token) -> None:
    assert isinstance(token.value, Keyword | PreprocessorKeyword)
    if isinstance(token.value, PreprocessorKeyword):
        raise ParserDirtyNonPreprocessedTokenError(token=token)
    TOP_LEVEL_KEYWORD = (  # noqa: N806
        Keyword.INLINE,
        Keyword.EXTERN,
        Keyword.FUNCTION,
        Keyword.GLOBAL,
    )
    if context.is_top_level:
        if token.value not in (
            *TOP_LEVEL_KEYWORD,
            Keyword.END,
            Keyword.VARIABLE_DEFINE,
        ):
            msg = f"{token.value.name} expected to be not at top level! (temp-assert)"
            raise NotImplementedError(msg)
    elif token.value in TOP_LEVEL_KEYWORD:
        msg = f"{token.value.name} expected to be at top level! (temp-assert)"
        raise NotImplementedError(msg, token.location)
    match token.value:
        case Keyword.IF | Keyword.DO | Keyword.WHILE | Keyword.END:
            return consume_conditional_block_keyword_from_token(context, token)
        case Keyword.INLINE | Keyword.EXTERN | Keyword.FUNCTION | Keyword.GLOBAL:
            return _unpack_function_definition_from_token(context, token)
        case Keyword.FUNCTION_CALL:
            return _unpack_function_call_from_token(context, token)
        case Keyword.FUNCTION_RETURN:
            return context.push_new_operator(
                OperatorType.FUNCTION_RETURN,
                token,
                None,
                is_contextual=False,
            )
        case Keyword.TYPECAST:
            return unpack_typecast_from_token(context, token)
        case Keyword.VARIABLE_DEFINE:
            return _unpack_variable_definition_from_token(context)
        case _:
            assert_never(token.value)


def _unpack_variable_definition_from_token(
    context: ParserContext,
) -> None:
    varname_token = context.next_token()
    if not varname_token:
        raise NotImplementedError
    if varname_token.type != TokenType.IDENTIFIER:
        raise NotImplementedError
    assert isinstance(varname_token.value, str)

    typename = parser_type_from_tokenizer(context)

    varname = varname_token.text
    if varname in context.variables:
        raise ParserVariableNameAlreadyDefinedAsVariableError(
            token=varname_token,
            name=varname,
        )

    context.variables[varname] = Variable(name=varname, type=typename)


def _unpack_function_call_from_token(context: ParserContext, token: Token) -> None:
    name_token = context.next_token()
    if not name_token:
        raise NotImplementedError
    if name_token.type != TokenType.IDENTIFIER:
        msg = "expected function name as word after `call`"
        raise NotImplementedError(msg)
    name = name_token.text

    if not (function := context.functions.get(name)):
        raise ParserUnknownFunctionError(
            token=token,
            functions_available=context.functions.keys(),
            best_match=_best_match_for_word(context, token.text),
        )

    if function.emit_inline_body:
        assert not function.external_definition_link_to
        context.expand_from_inline_block(function)
        return

    context.push_new_operator(
        OperatorType.FUNCTION_CALL,
        token,
        name,
        is_contextual=False,
    )


def _unpack_function_definition_from_token(
    context: ParserContext,
    token: Token,
) -> None:
    definition = consume_function_definition(context, token)
    (
        token,
        function_name,
        parameters,
        return_type,
        modifier_is_inline,
        modifier_is_extern,
        modifier_is_global,
    ) = definition

    external_definition_link_to = function_name if modifier_is_extern else None

    if modifier_is_extern:
        context.add_function(
            Function(
                location=token.location,
                name=function_name,
                type_contract_in=parameters,
                type_contract_out=return_type,
                emit_inline_body=modifier_is_inline,
                external_definition_link_to=external_definition_link_to,
                is_global_linker_symbol=modifier_is_global,
                source=[],
                variables=OrderedDict(),
            ),
        )

        return

    opened_context_blocks = 0

    context_keywords = (Keyword.IF, Keyword.DO)
    end_keyword_text = KEYWORD_TO_NAME[Keyword.END]

    function_body_tokens: list[Token] = []
    while func_token := context.next_token():
        if func_token.type == TokenType.EOF:
            msg = "Expected function to be closed but got end of file"
            raise ValueError(msg)
        if func_token.type != TokenType.KEYWORD:
            function_body_tokens.append(func_token)
            continue

        if func_token.text == end_keyword_text:
            if opened_context_blocks <= 0:
                break
            opened_context_blocks -= 1

        is_context_keyword = WORD_TO_KEYWORD[func_token.text] in context_keywords
        if is_context_keyword:
            opened_context_blocks += 1

        function_body_tokens.append(func_token)

    new_context = ParserContext(
        _tokenizer=wrapped_tokenizer(t for t in function_body_tokens),
        functions=context.functions,
        parent=context,
    )
    source = _parse_from_context_into_operators(context=new_context).operators
    function = Function(
        location=func_token.location,
        name=function_name,
        type_contract_in=parameters,
        type_contract_out=return_type,
        emit_inline_body=modifier_is_inline,
        external_definition_link_to=external_definition_link_to,
        is_global_linker_symbol=modifier_is_global,
        source=source,
        variables=new_context.variables,
    )
    context.add_function(function)


def _try_unpack_function_from_token(
    context: ParserContext,
    token: Token,
) -> bool:
    assert token.type == TokenType.IDENTIFIER

    function = context.functions.get(token.text, None)
    if function:
        if function.emit_inline_body:
            context.expand_from_inline_block(function)
            return True
        context.push_new_operator(
            OperatorType.FUNCTION_CALL,
            token,
            function.name,
            is_contextual=False,
        )
        return True

    return False


def _push_string_operator(context: ParserContext, token: Token) -> None:
    assert isinstance(token.value, str)
    context.push_new_operator(
        type=OperatorType.PUSH_STRING,
        token=token,
        operand=token.value,
        is_contextual=False,
    )


def _push_integer_operator(context: ParserContext, token: Token) -> None:
    assert isinstance(token.value, int)
    context.push_new_operator(
        type=OperatorType.PUSH_INTEGER,
        token=token,
        operand=token.value,
        is_contextual=False,
    )


def _try_push_intrinsic_operator(context: ParserContext, token: Token) -> bool:
    assert isinstance(token.value, str)
    intrinsic = WORD_TO_INTRINSIC.get(token.value)

    if intrinsic is None:
        return False

    context.push_new_operator(
        type=OperatorType.INTRINSIC,
        token=token,
        operand=intrinsic,
        is_contextual=False,
    )
    return True
