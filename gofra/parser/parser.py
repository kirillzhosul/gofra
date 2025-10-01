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
from gofra.parser.functions import Function
from gofra.parser.functions.parser import consume_function_definition
from gofra.parser.types import parse_type
from gofra.parser.validator import validate_and_pop_entry_point
from gofra.parser.variables import Variable
from gofra.types.primitive.void import VoidType

from ._context import ParserContext
from .exceptions import (
    ParserDirtyNonPreprocessedTokenError,
    ParserEmptyIfBodyError,
    ParserEndAfterWhileError,
    ParserEndWithoutContextError,
    ParserExhaustiveContextStackError,
    ParserExpectedTypecastTypeError,
    ParserNoWhileBeforeDoError,
    ParserNoWhileConditionOperatorsError,
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


def parse_file(tokenizer: Generator[Token]) -> tuple[ParserContext, Function]:
    """Load file for parsing into operators."""
    context = _parse_from_context_into_operators(
        context=ParserContext(
            parent=None,
            tokenizer=tokenizer,
            functions={},
        ),
    )

    assert context.is_top_level
    assert not context.operators

    entry_point = validate_and_pop_entry_point(context)
    return context, entry_point


def _parse_from_context_into_operators(context: ParserContext) -> ParserContext:
    """Consumes token stream into language operators."""
    while token := next(context.tokenizer, None):
        _consume_token_for_parsing(
            token=token,
            context=context,
        )

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
        case TokenType.EOL:
            return None


def _consume_word_token(token: Token, context: ParserContext) -> None:
    if _try_unpack_function_from_token(context, token):
        return

    if _try_push_intrinsic_operator(context, token):
        return

    if _try_push_variable_reference(context, token):
        return

    raise ParserUnknownIdentifierError(
        word_token=token,
        names_available=context.functions.keys()
        | [v.name for v in _get_all_scopes_variables(context)],
        best_match=_best_match_for_word(context, token.text),
    )


def _search_variable_in_context_parents(
    child: ParserContext,
    variable: str,
) -> Variable | None:
    context_ref = child

    while True:
        if variable in context_ref.variables:
            return context_ref.variables[variable]

        if context_ref.parent:
            context_ref = context_ref.parent
            continue

        return None


def _get_all_scopes_variables(
    child: ParserContext,
) -> list[Variable]:
    context_ref = child
    variables: list[Variable] = []
    while True:
        variables.extend(context_ref.variables.values())

        if context_ref.parent:
            context_ref = context_ref.parent
            continue

        return variables


def _try_push_variable_reference(context: ParserContext, token: Token) -> bool:
    assert token.type == TokenType.IDENTIFIER

    varname = token.text

    if FEATURE_DEREFERENCE_VARIABLES_BY_DEFAULT:
        if varname.startswith("&"):
            # By default, all variables has implicit dereference
            # by marking them with & that behaviour is disabled and we obtain just an addr
            varname = varname.removeprefix("&")
            variable = _search_variable_in_context_parents(context, varname)
            if not variable:
                return False

            context.push_new_operator(
                type=OperatorType.PUSH_MEMORY_POINTER,
                token=token,
                operand=(varname, variable.type),
                is_contextual=False,
            )
            return True

        variable = _search_variable_in_context_parents(context, varname)
        if not variable:
            return False

        context.push_new_operator(
            type=OperatorType.PUSH_MEMORY_POINTER,
            token=token,
            operand=(varname, variable.type),
            is_contextual=False,
        )
        context.push_new_operator(
            type=OperatorType.INTRINSIC,
            token=token,
            operand=Intrinsic.MEMORY_LOAD,
            is_contextual=False,
        )
        return True

    variable = _search_variable_in_context_parents(context, varname)
    if not variable:
        return False
    context.push_new_operator(
        type=OperatorType.PUSH_MEMORY_POINTER,
        token=token,
        operand=(varname, variable.type),
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
            return _consume_conditional_keyword_from_token(context, token)
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
            return _unpack_typecast_from_token(context, token)
        case Keyword.VARIABLE_DEFINE:
            return _unpack_variable_definition_from_token(context)
        case _:
            assert_never(token.value)
            return None


def _unpack_variable_definition_from_token(
    context: ParserContext,
) -> None:
    varname_token = next(context.tokenizer, None)
    if not varname_token:
        raise NotImplementedError
    if varname_token.type != TokenType.IDENTIFIER:
        raise NotImplementedError
    assert isinstance(varname_token.value, str)

    typename_token = next(context.tokenizer, None)
    if not typename_token:
        raise NotImplementedError
    if typename_token.type != TokenType.IDENTIFIER:
        msg = f"expected identifier as typename but got {typename_token.type.name}"
        raise NotImplementedError(msg)
    assert isinstance(varname_token.value, str)

    typename = parse_type(typename_token.text)
    if not typename:
        msg = "Unknown typecast typename"
        raise ValueError(msg, typename_token.location)

    varname = varname_token.text
    if varname in context.variables:
        raise ParserVariableNameAlreadyDefinedAsVariableError(
            token=varname_token,
            name=varname,
        )
    context.variables[varname] = Variable(name=varname, type=typename)


def _unpack_typecast_from_token(context: ParserContext, token: Token) -> None:
    typename_token = next(context.tokenizer, None)
    if not typename_token:
        raise ParserExpectedTypecastTypeError(token=token)
    if typename_token.type != TokenType.IDENTIFIER:
        raise NotImplementedError
    assert isinstance(typename_token.value, str)

    typename = parse_type(typename_token.text)
    if not typename:
        msg = "Unknown typecast typename"
        raise ValueError(msg, typename_token.location)
    context.push_new_operator(
        OperatorType.TYPECAST,
        token,
        typename,
        is_contextual=False,
    )


def _unpack_function_call_from_token(context: ParserContext, token: Token) -> None:
    name_token = next(context.tokenizer, None)
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
        type_contract_in,
        type_contract_out,
        additional_modifiers,
        modifier_is_inline,
        modifier_is_extern,
        modifier_is_global,
    ) = definition

    assert len(type_contract_out) in (0, 1)
    type_contract_out = VoidType() if not type_contract_out else type_contract_out[0]
    external_definition_link_to = function_name if modifier_is_extern else None

    for additional_modifier in additional_modifiers:
        if additional_modifier.startswith("link[") and additional_modifier.endswith(
            "]",
        ):
            if not modifier_is_extern or external_definition_link_to is None:
                msg = "Cannot specify link to modifier for non-extern function"
                raise ValueError(msg)

            if external_definition_link_to != function_name:
                msg = "External definition already links to another name, did you supply 2 links modifiers?"
                raise ValueError(msg)
            external_definition_link_to = additional_modifier.removeprefix(
                "link[",
            ).removesuffix("]")
            continue
        msg = f"unknown modifier {additional_modifier}"
        raise ValueError(msg)
    if modifier_is_extern:
        context.add_function(
            Function(
                location=token.location,
                name=function_name,
                type_contract_in=type_contract_in,
                type_contract_out=type_contract_out,
                emit_inline_body=modifier_is_inline,
                external_definition_link_to=external_definition_link_to,
                is_global_linker_symbol=modifier_is_global,
                source=[],
                variables=OrderedDict(),
            ),
        )

        return

    opened_context_blocks = 0
    function_was_closed = False

    context_keywords = (Keyword.IF, Keyword.DO)
    end_keyword_text = KEYWORD_TO_NAME[Keyword.END]

    original_token = token
    function_body_tokens: list[Token] = []
    while func_token := next(context.tokenizer, None):
        if func_token.type != TokenType.KEYWORD:
            function_body_tokens.append(func_token)
            continue

        if func_token.text == end_keyword_text:
            if opened_context_blocks <= 0:
                function_was_closed = True
                break
            opened_context_blocks -= 1

        is_context_keyword = WORD_TO_KEYWORD[func_token.text] in context_keywords
        if is_context_keyword:
            opened_context_blocks += 1

        function_body_tokens.append(func_token)

    if not func_token:
        raise NotImplementedError
    if not function_was_closed:
        raise ValueError(original_token)

    new_context = ParserContext(
        tokenizer=(t for t in function_body_tokens),
        functions=context.functions,
        parent=context,
    )
    source = _parse_from_context_into_operators(context=new_context).operators
    function = Function(
        location=func_token.location,
        name=function_name,
        type_contract_in=type_contract_in,
        type_contract_out=type_contract_out,
        emit_inline_body=modifier_is_inline,
        external_definition_link_to=external_definition_link_to,
        is_global_linker_symbol=modifier_is_global,
        source=source,
        variables=new_context.variables,
    )
    context.add_function(function)


def _consume_conditional_keyword_from_token(
    context: ParserContext,
    token: Token,
) -> None:
    assert isinstance(token.value, Keyword)
    match token.value:
        case Keyword.IF:
            return context.push_new_operator(
                type=OperatorType.IF,
                token=token,
                operand=None,
                is_contextual=True,
            )
        case Keyword.DO:
            if not context.has_context_stack():
                raise ParserNoWhileBeforeDoError(do_token=token)

            operator_while_idx, context_while = context.pop_context_stack()
            if context_while.type != OperatorType.WHILE:
                raise ParserNoWhileBeforeDoError(do_token=token)

            while_condition_len = context.current_operator - operator_while_idx - 1
            if while_condition_len == 0:
                raise ParserNoWhileConditionOperatorsError(
                    while_token=context_while.token,
                )

            operator = context.push_new_operator(
                type=OperatorType.DO,
                token=token,
                operand=None,
                is_contextual=True,
            )
            context.operators[-1].jumps_to_operator_idx = operator_while_idx
            return operator
        case Keyword.WHILE:
            return context.push_new_operator(
                type=OperatorType.WHILE,
                token=token,
                operand=None,
                is_contextual=True,
            )
        case Keyword.END:
            if not context.has_context_stack():
                raise ParserEndWithoutContextError(end_token=token)

            context_operator_idx, context_operator = context.pop_context_stack()

            context.push_new_operator(
                type=OperatorType.END,
                token=token,
                operand=None,
                is_contextual=False,
            )
            prev_context_jumps_at = context_operator.jumps_to_operator_idx
            context_operator.jumps_to_operator_idx = context.current_operator - 1

            match context_operator.type:
                case OperatorType.DO:
                    context.operators[-1].jumps_to_operator_idx = prev_context_jumps_at
                case OperatorType.IF:
                    if_body_size = context.current_operator - context_operator_idx - 2
                    if if_body_size == 0:
                        raise ParserEmptyIfBodyError(if_token=context_operator.token)
                case OperatorType.WHILE:
                    raise ParserEndAfterWhileError(end_token=token)
                case _:
                    raise AssertionError

            return None
        case _:
            raise AssertionError


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
