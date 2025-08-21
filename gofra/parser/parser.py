from __future__ import annotations

from collections import deque
from difflib import get_close_matches
from pathlib import Path
from typing import TYPE_CHECKING

from gofra.lexer import (
    Keyword,
    Token,
    TokenType,
)
from gofra.lexer.keywords import KEYWORD_TO_NAME, WORD_TO_KEYWORD
from gofra.lexer.lexer import tokenize_file
from gofra.parser.functions import Function
from gofra.parser.functions.parser import consume_function_definition
from gofra.parser.validator import validate_and_pop_entry_point

from ._context import ParserContext
from .exceptions import (
    ParserEmptyIfBodyError,
    ParserEndAfterWhileError,
    ParserEndWithoutContextError,
    ParserExhaustiveContextStackError,
    ParserIncludeFileNotFoundError,
    ParserIncludeNonStringNameError,
    ParserIncludeNoPathError,
    ParserIncludeSelfFileMacroError,
    ParserMacroNonWordNameError,
    ParserMacroRedefinesLanguageDefinitionError,
    ParserMacroRedefinitionError,
    ParserNoMacroNameError,
    ParserNoWhileBeforeDoError,
    ParserNoWhileConditionOperatorsError,
    ParserUnclosedMacroError,
    ParserUnfinishedIfBlockError,
    ParserUnfinishedWhileDoBlockError,
    ParserUnknownWordError,
)
from .intrinsics import WORD_TO_INTRINSIC
from .operators import OperatorType

if TYPE_CHECKING:
    from collections.abc import Iterable


def _tokenize_tokens_reversed(path: Path) -> deque[Token]:
    return deque(list(tokenize_file(path))[::-1])


def parse_file(
    path: Path,
    include_search_directories: Iterable[Path],
) -> tuple[ParserContext, Function]:
    """Load file for parsing into operators (lex and then parse)."""
    # Consider reversing at generator side or smth like that
    tokens = _tokenize_tokens_reversed(path)
    context = _parse_from_context_into_operators(
        context=ParserContext(
            is_top_level=True,
            parsing_from_path=path,
            tokens=tokens,
            include_search_directories=include_search_directories,
            macros={},
            functions={},
            memories={},
        ),
    )

    assert context.is_top_level
    assert not context.operators

    entry_point = validate_and_pop_entry_point(context)
    return context, entry_point


def _parse_from_context_into_operators(context: ParserContext) -> ParserContext:
    """Consumes token stream into language operators."""
    while not context.tokens_exhausted():
        _consume_token_for_parsing(
            token=context.tokens.pop(),
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
        case TokenType.WORD:
            if _try_unpack_macro_or_inline_function_from_token(context, token):
                return None

            if _try_unpack_memory_reference_from_token(context, token):
                return None

            if _try_push_intrinsic_operator(context, token):
                return None

            raise ParserUnknownWordError(
                word_token=token,
                macro_names=context.macros.keys(),
                best_match=_best_match_for_word(context, token.text),
            )
        case TokenType.KEYWORD:
            return _consume_keyword_token(context, token)


def _best_match_for_word(context: ParserContext, word: str) -> str | None:
    matches = get_close_matches(word, WORD_TO_INTRINSIC.keys() | context.macros.keys())
    return matches[0] if matches else None


def _consume_keyword_token(context: ParserContext, token: Token) -> None:
    assert isinstance(token.value, Keyword)
    TOP_LEVEL_KEYWORD = (  # noqa: N806
        Keyword.INCLUDE,
        Keyword.INLINE,
        Keyword.EXTERN,
        Keyword.FUNCTION,
        Keyword.GLOBAL,
        Keyword.MEMORY,
        Keyword.MACRO,
    )
    if context.is_top_level and token.value not in (*TOP_LEVEL_KEYWORD, Keyword.END):
        msg = f"{token.value.name} expected to be not at top level! (temp-assert)"
        raise NotImplementedError(msg)
    if not context.is_top_level and token.value in TOP_LEVEL_KEYWORD:
        msg = f"{token.value.name} expected to be at top level! (temp-assert)"
        raise NotImplementedError(msg)
    match token.value:
        case Keyword.IF | Keyword.DO | Keyword.WHILE | Keyword.END:
            return _consume_conditional_keyword_from_token(context, token)
        case Keyword.MACRO:
            return _consume_macro_definition_into_token(context, token)
        case Keyword.INCLUDE:
            return _unpack_include_from_token(context, token)
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
        case Keyword.MEMORY:
            return _unpack_memory_segment_from_token(context, token)


def _unpack_memory_segment_from_token(context: ParserContext, token: Token) -> None:
    if context.tokens_exhausted():
        raise NotImplementedError

    memory_segment_name = context.tokens.pop()
    if memory_segment_name.type != TokenType.WORD:
        raise NotImplementedError
    assert isinstance(memory_segment_name.value, str)
    memory_segment_size = context.tokens.pop()
    if memory_segment_size.type != TokenType.INTEGER:
        raise NotImplementedError
    assert isinstance(memory_segment_size.value, int)

    # This is an definition only so we dont acquire reference/pointer
    context.memories[memory_segment_name.value] = memory_segment_size.value


def _consume_macro_definition_into_token(context: ParserContext, token: Token) -> None:
    if context.tokens_exhausted():
        raise ParserNoMacroNameError(macro_token=token)

    # Macro definition probably can overlap with function definition container

    macro_name_token = context.tokens.pop()
    macro_name = macro_name_token.text

    if macro_name_token.type != TokenType.WORD:
        raise ParserMacroNonWordNameError(macro_name_token=macro_name_token)

    if macro_name in context.macros:
        raise ParserMacroRedefinitionError(
            redefine_macro_name_token=macro_name_token,
            original_macro_location=context.macros[macro_name].location,
        )

    if macro_name in (WORD_TO_INTRINSIC.keys() | WORD_TO_KEYWORD.keys()):
        raise ParserMacroRedefinesLanguageDefinitionError(
            macro_token=macro_name_token,
            macro_name=macro_name,
        )

    macro = context.new_macro(from_token=token, name=macro_name)

    opened_context_blocks = 0
    macro_was_closed = False

    context_keywords = (Keyword.IF, Keyword.MACRO, Keyword.DO)
    end_keyword_text = KEYWORD_TO_NAME[Keyword.END]

    original_token = token
    while not context.tokens_exhausted():
        token = context.tokens.pop()

        if token.type != TokenType.KEYWORD:
            macro.push_token(token)
            continue

        if token.text == end_keyword_text:
            if opened_context_blocks <= 0:
                macro_was_closed = True
                break
            opened_context_blocks -= 1

        is_context_keyword = WORD_TO_KEYWORD[token.text] in context_keywords
        if is_context_keyword:
            opened_context_blocks += 1

        macro.push_token(token)

    if not macro_was_closed:
        raise ParserUnclosedMacroError(
            macro_token=original_token,
            macro_name=macro_name,
        )


def _unpack_function_call_from_token(context: ParserContext, token: Token) -> None:
    if context.tokens_exhausted():
        raise NotImplementedError

    extern_call_name_token = context.tokens.pop()
    extern_call_name = extern_call_name_token.text

    if extern_call_name_token.type != TokenType.WORD:
        raise NotImplementedError

    target_function = context.functions.get(extern_call_name)
    if not target_function:
        raise NotImplementedError

    if target_function.emit_inline_body:
        _try_unpack_macro_or_inline_function_from_token(context, extern_call_name_token)
        return

    context.push_new_operator(
        OperatorType.FUNCTION_CALL,
        token,
        extern_call_name,
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
        modifier_is_inline,
        modifier_is_extern,
        modifier_is_global,
    ) = definition

    if modifier_is_extern:
        if len(type_contract_out) > 1:
            msg = "Extern functions cannot have stack type contract consider using C FFI ABI"
            raise NotImplementedError(msg)
        context.new_function(
            from_token=token,
            name=function_name,
            type_contract_in=type_contract_in,
            type_contract_out=type_contract_out,
            emit_inline_body=modifier_is_inline,
            is_externally_defined=modifier_is_extern,
            is_global_linker_symbol=modifier_is_global,
            source=[],
        )
        return

    opened_context_blocks = 0
    function_was_closed = False

    context_keywords = (Keyword.IF, Keyword.DO)
    end_keyword_text = KEYWORD_TO_NAME[Keyword.END]

    original_token = token
    function_body_tokens: list[Token] = []
    while not context.tokens_exhausted():
        token = context.tokens.pop()

        if token.type != TokenType.KEYWORD:
            function_body_tokens.append(token)
            continue

        if token.text == end_keyword_text:
            if opened_context_blocks <= 0:
                function_was_closed = True
                break
            opened_context_blocks -= 1

        is_context_keyword = WORD_TO_KEYWORD[token.text] in context_keywords
        if is_context_keyword:
            opened_context_blocks += 1

        function_body_tokens.append(token)

    if not function_was_closed:
        raise ParserUnclosedMacroError(
            macro_token=original_token,
            macro_name=function_name,
        )

    new_context = ParserContext(
        parsing_from_path=context.parsing_from_path,
        is_top_level=False,
        include_search_directories=context.include_search_directories,
        tokens=function_body_tokens[::-1],  # type: ignore  # noqa: PGH003
        macros=context.macros,
        functions=context.functions,
        memories=context.memories,
    )
    context.new_function(
        from_token=token,
        name=function_name,
        type_contract_in=type_contract_in,
        type_contract_out=type_contract_out,
        emit_inline_body=modifier_is_inline,
        is_externally_defined=modifier_is_extern,
        is_global_linker_symbol=modifier_is_global,
        source=_parse_from_context_into_operators(context=new_context).operators,
    )


def _unpack_include_from_token(context: ParserContext, token: Token) -> None:
    if context.tokens_exhausted():
        raise ParserIncludeNoPathError(include_token=token)

    include_path_token = context.tokens.pop()
    include_path_raw = include_path_token.value

    if include_path_token.type != TokenType.STRING:
        raise ParserIncludeNonStringNameError(include_path_token=include_path_token)

    assert isinstance(include_path_raw, str)
    requested_include_path = Path(include_path_raw)

    if requested_include_path.absolute() == context.parsing_from_path.absolute():
        raise ParserIncludeSelfFileMacroError

    include_path = _resolve_real_import_path(requested_include_path, context)

    if include_path is None:
        raise ParserIncludeFileNotFoundError(
            include_token=token,
            include_path=requested_include_path,
        )

    already_included_sources = (n.resolve() for n in context.included_source_paths)
    if include_path.resolve() in already_included_sources:
        return

    context.included_source_paths.add(include_path)
    context.tokens.extend(_tokenize_tokens_reversed(include_path))


def _resolve_real_import_path(
    requested_include_path: Path,
    context: ParserContext,
) -> Path | None:
    if requested_include_path.exists():
        return requested_include_path

    for include_search_directory in context.include_search_directories:
        load_from_path = include_search_directory.joinpath(requested_include_path)
        if load_from_path.exists():
            return load_from_path

    return None


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


def _try_unpack_memory_reference_from_token(
    context: ParserContext,
    token: Token,
) -> bool:
    assert token.type == TokenType.WORD

    memory_name = token.text
    if memory_name not in context.memories:
        return False
    context.push_new_operator(
        type=OperatorType.PUSH_MEMORY_POINTER,
        token=token,
        operand=memory_name,
        is_contextual=False,
    )
    return True


def _try_unpack_macro_or_inline_function_from_token(
    context: ParserContext,
    token: Token,
) -> bool:
    assert token.type == TokenType.WORD

    inline_block = context.macros.get(token.text, None) or context.functions.get(
        token.text,
        None,
    )
    if inline_block:
        if isinstance(inline_block, Function) and (
            not inline_block.emit_inline_body or inline_block.is_externally_defined
        ):
            raise NotImplementedError(
                "use `call` to call an function, obtaining an function is not implemented yet"
            )
        context.expand_from_inline_block(inline_block)

    return bool(inline_block)


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
