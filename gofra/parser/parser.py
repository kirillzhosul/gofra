from __future__ import annotations

from difflib import get_close_matches
from pathlib import Path
from typing import TYPE_CHECKING, assert_never

from gofra.consts import GOFRA_ENTRY_POINT
from gofra.feature_flags import FEATURE_DEREFERENCE_VARIABLES_BY_DEFAULT
from gofra.hir.function import Function
from gofra.hir.module import Module
from gofra.hir.variable import Variable, VariableScopeClass, VariableStorageClass
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
from gofra.parser.typecast import unpack_typecast_from_token
from gofra.parser.types import parser_type_from_tokenizer
from gofra.parser.variables import (
    get_all_scopes_variables,
    search_variable_in_context_parents,
)
from gofra.types.composite.array import ArrayType
from gofra.types.composite.structure import StructureType

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

    from gofra.types._base import Type


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
    struct_field_accessor = None

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

    accessor_token = context.peek_token()
    if (
        accessor_token.type == TokenType.DOT
        and not accessor_token.has_trailing_whitespace
    ):
        _ = context.next_token()  # Consume DOT
        if array_index_at is not None:
            msg = "Referencing an field from an struct within array accessor is not implemented yet."
            raise NotImplementedError(msg)
        struct_field_accessor = context.next_token()
        if struct_field_accessor.type != TokenType.IDENTIFIER:
            msg = f"Expected struct field accessor to be an identifier, but got {struct_field_accessor.type.name}"
            raise ValueError(msg)

    variable = search_variable_in_context_parents(context, varname)
    if not variable:
        return False

    context.push_new_operator(
        type=OperatorType.PUSH_VARIABLE_ADDRESS,
        token=token,
        operand=varname,
    )

    if struct_field_accessor:
        if not is_reference:
            msg = "Struct field accessors are implemented only for references."
            raise NotImplementedError(msg)
        if not isinstance(variable.type, StructureType):
            msg = "cannot get field-offset-of (e.g .field) for non-structure types."
            raise ValueError(msg)

        field = struct_field_accessor.text
        if field not in variable.type.fields:
            msg = f"Field accessor {field} at {token.location} is unknown for structure {variable.type.name}"
            raise ValueError(msg)

        context.push_new_operator(
            type=OperatorType.STRUCT_FIELD_OFFSET,
            token=token,
            operand=f"{variable.type.name}.{field}",
        )

    if array_index_at is not None:
        if not isinstance(variable.type, ArrayType):
            msg = "cannot get index-of (e.g []) for non-array types."
            raise ValueError(msg)

        if array_index_at < 0:
            msg = "Negative indexing inside arrays is prohibited"
            raise ValueError(msg)

        if variable.type.is_index_oob(array_index_at):
            msg = f"OOB (out-of-bounds) for array access `{token.text}` at {token.location}, array has {variable.type.elements_count} elements"
            raise ValueError(msg)

        shift_in_bytes = variable.type.get_index_offset(array_index_at)
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
            return _unpack_variable_definition_from_token(context)
        case Keyword.SYSCALL:
            return context.push_new_operator(
                type=OperatorType.SYSCALL,
                token=token,
                operand=int(token.text[-1]),
            )
        case Keyword.STRUCT:
            return _unpack_structure_definition_from_token(context)
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


def _unpack_structure_definition_from_token(context: ParserContext) -> None:
    name_token = context.next_token()
    if name_token.type != TokenType.IDENTIFIER:
        msg = f"Expected structure name at {name_token.location} to be an identifier but got {name_token.type.name}"
        raise ValueError(msg)

    name = name_token.text

    if context.name_is_already_taken(name):
        msg = f"Structure name {name} is already taken by other definition"
        raise ValueError(msg)

    fields: dict[str, Type] = {}
    fields_ordering: list[str] = []
    while token := context.next_token():
        if token.type == TokenType.KEYWORD and token.value == Keyword.END:
            # End of structure block definition
            break
        field_name_token = token

        if field_name_token.type != TokenType.IDENTIFIER:
            msg = f"Expected structure field name at {field_name_token.location} to be an identifier but got {field_name_token.type.name}"
            raise ValueError(msg)
        field_name = field_name_token.text
        field_type = parser_type_from_tokenizer(context)
        fields_ordering.append(field_name)
        fields[field_name] = field_type

    struct = StructureType(
        name=name,
        fields=fields,
        cpu_alignment_in_bytes=0,
        fields_ordering=fields_ordering,
    )
    context.structs[name] = struct


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

    if context.name_is_already_taken(varname):
        msg = f"Variable name {varname} is already taken by other definition"
        raise ValueError(msg)

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
