from __future__ import annotations

from difflib import get_close_matches
from typing import TYPE_CHECKING, assert_never

from libgofra.consts import GOFRA_ENTRY_POINT
from libgofra.feature_flags import FEATURE_ALLOW_FPU
from libgofra.hir.function import Function
from libgofra.hir.module import Module
from libgofra.hir.variable import Variable, VariableScopeClass, VariableStorageClass
from libgofra.lexer import (
    Keyword,
    Token,
    TokenType,
)
from libgofra.lexer.keywords import PreprocessorKeyword
from libgofra.parser.conditional_blocks import (
    consume_conditional_block_keyword_from_token,
)
from libgofra.parser.errors.keyword_in_without_loop_block import (
    KeywordInWithoutLoopBlockError,
)
from libgofra.parser.errors.local_level_keyword_in_global_scope import (
    LocalLevelKeywordInGlobalScopeError,
)
from libgofra.parser.errors.top_level_expected_no_operators import (
    TopLevelExpectedNoOperatorsError,
)
from libgofra.parser.errors.top_level_keyword_in_local_scope import (
    TopLevelKeywordInLocalScopeError,
)
from libgofra.parser.functions.parser import (
    consume_function_body_tokens,
    consume_function_definition,
)
from libgofra.parser.structures import unpack_structure_definition_from_token
from libgofra.parser.type_parser import (
    parse_concrete_type_from_tokenizer,
)
from libgofra.parser.typecast import unpack_typecast_from_token
from libgofra.parser.typedef import unpack_type_definition_from_token
from libgofra.parser.variable_accessor import try_push_variable_reference
from libgofra.parser.variable_definition import (
    unpack_variable_definition_from_token,
)
from libgofra.types.composite.string import StringType

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
    if context.operators:
        raise TopLevelExpectedNoOperatorsError(context.operators[0])

    _inject_context_module_runtime_definitions(context)
    return Module(
        path=path,
        functions=context.functions,
        variables=context.variables,
        structures=context.structs,
    )


def _inject_context_module_runtime_definitions(context: ParserContext) -> None:
    """Inject definitions that must be known at parse stage."""
    string_t = StringType()
    context.structs[string_t.name] = string_t


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
        _, unclosed_operator, *_ = context.pop_context_stack()
        match unclosed_operator.type:
            case OperatorType.CONDITIONAL_DO | OperatorType.CONDITIONAL_WHILE:
                raise ParserUnfinishedWhileDoBlockError(token=unclosed_operator.token)
            case OperatorType.CONDITIONAL_IF:
                raise ParserUnfinishedIfBlockError(if_token=unclosed_operator.token)
            case _:
                raise ParserExhaustiveContextStackError


def _consume_token_for_parsing(token: Token, context: ParserContext) -> None:  # noqa: PLR0911
    match token.type:
        case TokenType.INTEGER | TokenType.CHARACTER:
            return _push_integer_operator(context, token)
        case TokenType.FLOAT:
            if not FEATURE_ALLOW_FPU:
                msg = "FPU is disabled as feature for being in unstable test stage, try enable `FEATURE_ALLOW_FPU` to access FP."
                raise ValueError(msg)
            return _push_float_operator(context, token)
        case TokenType.STRING:
            return _push_string_operator(context, token)
        case TokenType.IDENTIFIER:
            return _consume_word_token(token, context)
        case TokenType.KEYWORD:
            return _consume_keyword_token(context, token)
        case TokenType.EOL | TokenType.EOF:
            return None
        case TokenType.STAR:
            assert not context.is_top_level
            context.push_new_operator(OperatorType.ARITHMETIC_MULTIPLY, token=token)
            return None
        case TokenType.SEMICOLON:
            # Treat semicolon as simple line break should be fine except this may be caught in some complex constructions checks
            return None
        case (
            TokenType.LBRACKET
            | TokenType.RBRACKET
            | TokenType.LPAREN
            | TokenType.RPAREN
            | TokenType.DOT
            | TokenType.COMMA
            | TokenType.COLON
            | TokenType.RCURLY
            | TokenType.LCURLY
            | TokenType.ASSIGNMENT
        ):
            msg = f"Got {token.type.name} ({token.location}) in form of an single parser-expression (non-composite). This token (as other symbol-defined ones) must occur only in composite expressions (e.g function signature, type constructions)."
            raise ValueError(msg)
        case _:
            assert_never(token.type)


def _consume_word_token(token: Token, context: ParserContext) -> None:
    if _try_unpack_function_call_from_identifier_token(context, token):
        return

    if _try_push_intrinsic_operator(context, token):
        return

    if try_push_variable_reference(context, token):
        return

    raise ParserUnknownIdentifierError(
        word_token=token,
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


def _consume_keyword_token(context: ParserContext, token: Token) -> None:  # noqa: PLR0911
    if isinstance(token.value, PreprocessorKeyword):
        raise ParserDirtyNonPreprocessedTokenError(token=token)
    assert isinstance(token.value, Keyword)

    TOP_LEVEL_KEYWORD = (  # noqa: N806
        Keyword.INLINE,
        Keyword.EXTERN,
        Keyword.NO_RETURN,
        Keyword.FUNCTION,
        Keyword.GLOBAL,
        Keyword.STRUCT,
        Keyword.TYPE_DEFINE,
    )

    BOTH_LEVEL_KEYWORD = (  # noqa: N806
        Keyword.CONST,
        Keyword.END,
        Keyword.VARIABLE_DEFINE,
    )
    if context.is_top_level:
        if token.value not in (*TOP_LEVEL_KEYWORD, *BOTH_LEVEL_KEYWORD):
            raise LocalLevelKeywordInGlobalScopeError(token)
    elif token.value in TOP_LEVEL_KEYWORD:
        raise TopLevelKeywordInLocalScopeError(token)

    match token.value:
        case Keyword.IF | Keyword.DO | Keyword.WHILE | Keyword.END | Keyword.FOR:
            return consume_conditional_block_keyword_from_token(context, token)
        case (
            Keyword.INLINE
            | Keyword.EXTERN
            | Keyword.FUNCTION
            | Keyword.GLOBAL
            | Keyword.NO_RETURN
        ):
            return _unpack_function_definition_from_token(context, token)
        case Keyword.FUNCTION_CALL:
            return _unpack_function_call_from_token(context, token)
        case Keyword.FUNCTION_RETURN:
            return context.push_new_operator(OperatorType.FUNCTION_RETURN, token=token)
        case Keyword.TYPE_CAST:
            return unpack_typecast_from_token(context, token)
        case Keyword.VARIABLE_DEFINE | Keyword.CONST:
            return unpack_variable_definition_from_token(context, token)
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
        case Keyword.SIZEOF:
            return _unpack_sizeof_from_token(context, token)
        case Keyword.IN:
            raise KeywordInWithoutLoopBlockError(token)
        case Keyword.TYPE_DEFINE:
            if (
                (peeked := context.peek_token())
                and peeked.type == TokenType.KEYWORD
                and peeked.value == Keyword.STRUCT
            ):
                # `type struct ...` must be treated as structure
                context.advance_token()
                return unpack_structure_definition_from_token(context)

            return unpack_type_definition_from_token(context)
        case _:
            assert_never(token.value)


def _unpack_sizeof_from_token(context: ParserContext, token: Token) -> None:
    sizeof_type = parse_concrete_type_from_tokenizer(
        context,
        allow_inferring_variable_types=True,
    )
    context.push_new_operator(
        OperatorType.PUSH_INTEGER,
        token=token,
        operand=sizeof_type.size_in_bytes,
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
    f_header_def = consume_function_definition(context, token)

    params = [p[1] for p in f_header_def.parameters]

    if f_header_def.qualifiers.is_extern:
        function = Function.create_external(
            name=f_header_def.name,
            defined_at=token.location,
            parameters=params,
            return_type=f_header_def.return_type,
        )
        function.is_no_return = f_header_def.qualifiers.is_no_return
        context.add_function(function)
        return

    if context.name_is_already_taken(f_header_def.name):
        msg = f"Function name {f_header_def.name} is already taken by other definition"
        raise ValueError(msg)

    new_context = ParserContext(
        _tokenizer=consume_function_body_tokens(context),
        functions=context.functions,
        parent=context,
    )

    param_names = [p[0] for p in f_header_def.parameters]
    if any(param_names) and not all(param_names):
        msg = f"Either all parameters must be named or none! {token.location}"
        raise ValueError(msg)

    for param_name, param_type in reversed(f_header_def.parameters):
        if not param_name:
            continue
        new_context.variables[param_name] = Variable(
            name=param_name,
            defined_at=token.location,
            is_constant=False,
            storage_class=VariableStorageClass.STACK,
            scope_class=VariableScopeClass.FUNCTION,
            type=param_type,
            initial_value=None,
        )
        new_context.push_new_operator(
            OperatorType.LOAD_PARAM_ARGUMENT,
            token,
            operand=param_name,
        )
    _parse_from_context_into_operators(context=new_context)

    if f_header_def.qualifiers.is_inline:
        assert not new_context.variables, "Inline functions cannot have local variables"
        function = Function.create_internal_inline(
            name=f_header_def.name,
            defined_at=token.location,
            operators=new_context.operators,
            return_type=f_header_def.return_type,
            parameters=params,
        )
        function.is_no_return = f_header_def.qualifiers.is_no_return
        context.add_function(function)
        return
    if f_header_def.name == GOFRA_ENTRY_POINT:
        f_header_def.qualifiers.is_global = True

    function = Function.create_internal(
        name=f_header_def.name,
        defined_at=token.location,
        operators=new_context.operators,
        variables=new_context.variables,
        parameters=params,
        return_type=f_header_def.return_type,
        is_global=f_header_def.qualifiers.is_global,
        is_leaf=new_context.is_leaf_context,
    )
    function.is_no_return = f_header_def.qualifiers.is_no_return
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


def _push_float_operator(context: ParserContext, token: Token) -> None:
    assert isinstance(token.value, float)
    context.push_new_operator(
        type=OperatorType.PUSH_FLOAT,
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
