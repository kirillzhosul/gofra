from __future__ import annotations

from difflib import get_close_matches
from typing import TYPE_CHECKING, assert_never

from gofra.feature_flags import FEATURE_DEREFERENCE_VARIABLES_BY_DEFAULT
from gofra.hir.function import Function
from gofra.hir.variable import Variable, VariableScopeClass, VariableStorageClass
from gofra.lexer import (
    Keyword,
    Token,
    TokenType,
)
from gofra.lexer.keywords import KEYWORD_TO_NAME, WORD_TO_KEYWORD, PreprocessorKeyword
from gofra.parser.conditional_blocks import consume_conditional_block_keyword_from_token
from gofra.parser.functions.parser import consume_function_definition
from gofra.parser.typecast import unpack_typecast_from_token
from gofra.parser.types import parser_type_from_tokenizer
from gofra.parser.validator import validate_and_pop_entry_point
from gofra.parser.variables import (
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
from .operators import IDENTIFIER_TO_OPERATOR_TYPE, OperatorType

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
        f"Expected NO operators on top level, first one is at {context.operators[0].location}"
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
            case OperatorType.CONDITIONAL_DO | OperatorType.CONDITIONAL_WHILE:
                raise ParserUnfinishedWhileDoBlockError(token=unclosed_operator.token)
            case OperatorType.CONDITIONAL_IF:
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
        type=OperatorType.PUSH_VARIABLE_ADDRESS,
        token=token,
        operand=varname,
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
            )
            context.push_new_operator(
                type=OperatorType.ARITHMETIC_PLUS,
                token=token,
            )

    if not is_reference:
        context.push_new_operator(
            type=OperatorType.MEMORY_VARIABLE_READ,
            token=token,
        )
    return True


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
            return _unpack_variable_definition_from_token(context)
        case Keyword.SYSCALL:
            return context.push_new_operator(
                type=OperatorType.SYSCALL,
                token=token,
                operand=int(token.text[-1]),
            )
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


def _unpack_variable_definition_from_token(
    context: ParserContext,
) -> None:
    varname_token = context.next_token()
    if varname_token.type != TokenType.IDENTIFIER:
        msg = "Expected variable name after variable keyword"
        raise ValueError(msg)
    assert isinstance(varname_token.value, str)

    typename = parser_type_from_tokenizer(context)
    varname = varname_token.text

    if varname in context.variables:
        raise ParserVariableNameAlreadyDefinedAsVariableError(
            token=varname_token,
            name=varname,
        )

    storage_class = (
        VariableStorageClass.STATIC
        if context.is_top_level
        else VariableStorageClass.STACK
    )
    scope_class = (
        VariableScopeClass.GLOBAL
        if context.is_top_level
        else VariableScopeClass.FUNCTION
    )
    context.variables[varname] = Variable(
        name=varname,
        type=typename,
        defined_at=varname_token.location,
        scope_class=scope_class,
        storage_class=storage_class,
    )


def _unpack_function_call_from_token(context: ParserContext, token: Token) -> None:
    name_token = context.next_token()
    if name_token.type != TokenType.IDENTIFIER:
        msg = "expected function name as identifier after `call`"
        raise ValueError(msg)

    name = name_token.text
    function = context.functions.get(name)

    if not function:
        raise ParserUnknownFunctionError(
            token=token,
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
        context.add_function(
            Function(
                name=function_name,
                defined_at=token.location,
                operators=[],
                variables={},
                parameters=parameters,
                return_type=return_type,
                is_inline=modifier_is_inline,
                is_external=modifier_is_extern,
                is_global=modifier_is_global,
                is_leaf=False,
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
        name=function_name,
        defined_at=token.location,
        operators=source,
        variables=new_context.variables,
        parameters=parameters,
        return_type=return_type,
        is_inline=modifier_is_inline,
        is_external=modifier_is_extern,
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
