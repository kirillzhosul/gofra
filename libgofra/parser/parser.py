from __future__ import annotations

from difflib import get_close_matches
from pathlib import Path
from typing import TYPE_CHECKING, assert_never

from libgofra.feature_flags import FEATURE_ALLOW_FPU, FEATURE_ALLOW_MODULES
from libgofra.hir.function import Function, Visibility
from libgofra.hir.operator import FunctionCallOperand
from libgofra.hir.variable import Variable, VariableScopeClass, VariableStorageClass
from libgofra.lexer import (
    Keyword,
    Token,
    TokenType,
)
from libgofra.lexer.keywords import PreprocessorKeyword
from libgofra.parser.errors.general_name_conflict_error import (
    GeneralNameHolderConflictError,
)
from libgofra.parser.errors.keyword_in_without_loop_block import (
    KeywordInWithoutLoopBlockError,
)
from libgofra.parser.errors.lambda_with_extern_attr import LambdaWithExternAttrError
from libgofra.parser.errors.lambda_with_inline_attr import LambdaWithInlineAttrError
from libgofra.parser.errors.lambda_with_visibility_attr import (
    LambdaWithVisibilityAttrError,
)
from libgofra.parser.errors.local_level_keyword_in_global_scope import (
    LocalLevelKeywordInGlobalScopeError,
)
from libgofra.parser.errors.private_symbol_access import PrivateSymbolAccessError
from libgofra.parser.errors.top_level_expected_no_operators import (
    TopLevelExpectedNoOperatorsError,
)
from libgofra.parser.errors.top_level_keyword_in_local_scope import (
    TopLevelKeywordInLocalScopeError,
)
from libgofra.parser.exprs.compile_time_error import unpack_compile_time_error
from libgofra.parser.exprs.conditional_blocks import (
    consume_conditional_block_keyword_from_token,
)
from libgofra.parser.exprs.primitives import (
    push_float_operator,
    push_integer_operator,
    push_string_operator,
    try_push_intrinsic_operator,
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
from libgofra.types.composite.function import FunctionType
from libgofra.types.composite.structure import StructureType

from ._context import ParserScope
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
    from collections.abc import Callable, Generator

    from libgofra.hir.module import Module
    from libgofra.types._base import Type


TOP_LEVEL_KEYWORD = (
    Keyword.ATTR_FUNC_INLINE,
    Keyword.ATTR_FUNC_EXTERN,
    Keyword.ATTR_FUNC_NO_RETURN,
    Keyword.ATTR_FUNC_PUBLIC,
    Keyword.ATTR_FUNC_NAKED,
    Keyword.ATTR_STRUCT_REORDER,
    Keyword.ATTR_STRUCT_PACKED,
    Keyword.FUNCTION,
    Keyword.STRUCT,
    Keyword.TYPE_DEFINE,
    Keyword.MODULE_IMPORT,
)

BOTH_LEVEL_KEYWORD = (
    Keyword.CONST_DEFINE,
    Keyword.END,
    Keyword.VARIABLE_DEFINE,
    Keyword.COMPILE_TIME_ERROR,
)


def parse_module_from_tokenizer(
    module: Module,
    tokenizer: Generator[Token],
    *,
    rt_array_oob_check: bool = False,
    entry_point_name: str,
    on_import_request: Callable[[str, Path], None],
) -> Module:
    """Load file for parsing into operators."""
    context = ParserScope(
        module=module,
        _tokenizer=tokenizer,
        rt_array_oob_check=rt_array_oob_check,
        entry_point_name=entry_point_name,
        on_import_request=on_import_request,
    )
    _parse_from_context_into_operators(context=context)

    assert context.is_top_level, (
        "Parser context in result of parsing must an top level, bug in a parser"
    )
    if context.operators:
        raise TopLevelExpectedNoOperatorsError(context.operators[0])

    context.merge_scope_into_module(module)

    _validate_function_existence_and_visibility(root=module, module=module)

    return module


def _validate_function_existence_and_visibility(root: Module, module: Module) -> None:
    # TODO(@kirillzhosul): This must be refactored - as implemented new dependency system
    for func in module.executable_functions:
        for op in func.operators:
            if op.type == OperatorType.FUNCTION_CALL:
                assert isinstance(op.operand, FunctionCallOperand), op.operand
                resolved_symbol = module.resolve_function_dependency(
                    op.operand.module,
                    op.operand.get_name(),
                )
                if resolved_symbol is None:
                    print(f"[help] Tried to resolve import from {op.operand.module}")
                    raise ParserUnknownFunctionError(
                        at=op.token.location,
                        name=op.operand.get_name(),
                        functions_available=[],
                        best_match=None,
                    )
                if op.operand.module is not None:
                    func_owner_mod = module.dependencies[op.operand.module]
                    if (
                        not resolved_symbol.is_public
                        and func_owner_mod.path != root.path
                    ):
                        raise PrivateSymbolAccessError(
                            defined_at=resolved_symbol.defined_at,
                            symbol_name=resolved_symbol.name,
                            call_site=op.location,
                            target_module=op.operand.module,
                        )

    for children_module in module.dependencies.values():
        _validate_function_existence_and_visibility(root=root, module=children_module)


def _parse_from_context_into_operators(context: ParserScope) -> None:
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


def _consume_token_for_parsing(token: Token, context: ParserScope) -> None:  # noqa: PLR0911
    match token.type:
        case TokenType.INTEGER | TokenType.CHARACTER:
            return push_integer_operator(context, token)
        case TokenType.FLOAT:
            if not FEATURE_ALLOW_FPU:
                msg = "FPU is disabled as feature for being in unstable test stage, try enable `FEATURE_ALLOW_FPU` to access FP."
                raise ValueError(msg)
            return push_float_operator(context, token)
        case TokenType.STRING:
            return push_string_operator(context, token)
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


def _consume_word_token(token: Token, context: ParserScope) -> None:
    if try_push_intrinsic_operator(context, token):
        return

    if _try_unpack_function_call_from_identifier_token(context, token):
        return

    if try_push_variable_reference(context, token):
        return

    raise ParserUnknownIdentifierError(
        word_token=token,
        best_match=_best_match_for_word(context, token.text),
    )


def _best_match_for_word(context: ParserScope, word: str) -> str | None:
    matches = get_close_matches(
        word,
        IDENTIFIER_TO_OPERATOR_TYPE.keys()
        | context.functions.keys()
        | context.variables.keys(),
    )
    return matches[0] if matches else None


def _consume_keyword_token(context: ParserScope, token: Token) -> None:  # noqa: PLR0911
    if isinstance(token.value, PreprocessorKeyword):
        raise ParserDirtyNonPreprocessedTokenError(token=token)
    assert isinstance(token.value, Keyword)

    if context.is_top_level:
        if token.value not in (*TOP_LEVEL_KEYWORD, *BOTH_LEVEL_KEYWORD):
            raise LocalLevelKeywordInGlobalScopeError(token)
    elif token.value in TOP_LEVEL_KEYWORD:
        raise TopLevelKeywordInLocalScopeError(token)

    match token.value:
        case Keyword.IF | Keyword.DO | Keyword.WHILE | Keyword.END | Keyword.FOR:
            return consume_conditional_block_keyword_from_token(context, token)
        case (
            Keyword.FUNCTION
            | Keyword.ATTR_FUNC_INLINE
            | Keyword.ATTR_FUNC_EXTERN
            | Keyword.ATTR_FUNC_PUBLIC
            | Keyword.ATTR_FUNC_NO_RETURN
            | Keyword.ATTR_FUNC_NAKED
        ):
            return _unpack_function_definition_from_token(context, token)
        case Keyword.FUNCTION_CALL:
            return _unpack_function_call_from_token(context, token)
        case Keyword.FUNCTION_RETURN:
            return context.push_new_operator(OperatorType.FUNCTION_RETURN, token=token)
        case Keyword.TYPE_CAST:
            return unpack_typecast_from_token(context, token)
        case Keyword.VARIABLE_DEFINE | Keyword.CONST_DEFINE:
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
        case Keyword.OFFSET_OF:
            return _unpack_offset_of_from_token(context, token)
        case Keyword.POINTER_OF_PROC:
            return _unpack_pointer_of_proc(context, token)
        case Keyword.IN:
            raise KeywordInWithoutLoopBlockError(token)
        case Keyword.INLINE_RAW_ASM:
            return _unpack_inline_raw_assembly(context, token)
        case Keyword.COMPILE_TIME_ERROR:
            return unpack_compile_time_error(context, token)
        case Keyword.MODULE_IMPORT:
            return _unpack_import(context, token)
        case Keyword.ALIGN_OF:
            return _unpack_align_of(context, token)
        case Keyword.LAMBDA_DEF:
            return _unpack_anonymous_lambda_function_from_token(context, token)
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
        case Keyword.AS:
            msg = f"As keyword may used only in import statements for now at {token.location}"
            raise ValueError(msg)
        case Keyword.ATTR_STRUCT_PACKED | Keyword.ATTR_STRUCT_REORDER:
            raise ValueError
        case _:
            assert_never(token.value)


def _new_function_scope(
    parent: ParserScope,
    token: Token,
    parameters: list[tuple[str, Type]],
) -> ParserScope:
    new_scope = ParserScope.from_parent(
        parent,
        tokenizer=consume_function_body_tokens(parent),
    )

    for param_name, param_type in reversed(parameters):
        if not param_name:
            continue
        if param_name == "_":
            new_scope.push_new_operator(OperatorType.STACK_DROP, token=token)
            continue
        new_scope.variables[param_name] = Variable(
            name=param_name,
            defined_at=token.location,
            is_constant=False,
            storage_class=VariableStorageClass.STACK,
            scope_class=VariableScopeClass.FUNCTION,
            type=param_type,
            initial_value=None,
        )

        new_scope.push_new_operator(
            OperatorType.LOAD_PARAM_ARGUMENT,
            token,
            operand=param_name,
        )
    _parse_from_context_into_operators(context=new_scope)

    return new_scope


def _unpack_anonymous_lambda_function_from_token(
    context: ParserScope,
    token: Token,
) -> None:
    assert token.type == TokenType.KEYWORD
    assert token.value == Keyword.LAMBDA_DEF
    assert not context.is_top_level

    def _parse_and_spill_enclosures() -> Function:
        f_header_def = consume_function_definition(context, context.next_token())

        if f_header_def.qualifiers.is_extern:
            raise LambdaWithExternAttrError(at=token.location)

        if f_header_def.qualifiers.is_inline:
            raise LambdaWithInlineAttrError(at=token.location)

        if f_header_def.qualifiers.is_public:
            raise LambdaWithVisibilityAttrError(at=token.location)

        # TODO(@kirillzhosul): doesn't anonymous functions do not hold their names?
        if context.query_name_holder(f_header_def.name):
            msg = f"Function name {f_header_def.name} is already taken by other definition"
            raise ValueError(msg)

        new_context = _new_function_scope(context, token, f_header_def.parameters)

        function = Function.create_internal(
            name=f_header_def.name,
            defined_at=token.location,
            operators=new_context.operators,
            variables=new_context.variables,
            parameters=f_header_def.parameters,
            return_type=f_header_def.return_type,
        )
        function.attrs.leaf = new_context.is_leaf_context
        function.attrs.naked = f_header_def.qualifiers.is_naked
        function.attrs.no_return = f_header_def.qualifiers.is_no_return

        function.attrs.visibility = Visibility.PRIVATE

        assert context.module
        function.module = context.module
        assert not context.is_top_level
        context.add_function(function)
        return function

    function = _parse_and_spill_enclosures()
    context.push_new_operator(
        OperatorType.PUSH_FUNCTION_POINTER,
        token=token,
        operand=FunctionCallOperand(None, function),
    )


def _unpack_align_of(context: ParserScope, token: Token) -> None:
    alignment_of_type = parse_concrete_type_from_tokenizer(
        context,
        allow_inferring_variable_types=False,  # ? must be
    )

    context.push_new_operator(
        OperatorType.PUSH_INTEGER,
        token=token,
        operand=alignment_of_type.alignment,
    )


def _unpack_pointer_of_proc(context: ParserScope, token: Token) -> None:
    function_name_token = context.next_token()
    if function_name_token.type != TokenType.IDENTIFIER:
        msg = f"Expected identifier as function name for pointer-of-proc at {token.location} but got {function_name_token.type}"
        raise ValueError(msg)

    function_name = function_name_token.text
    assert function_name in context.functions
    function = context.functions[function_name]

    context.push_new_operator(
        OperatorType.PUSH_FUNCTION_POINTER,
        token=token,
        operand=FunctionCallOperand(None, function),
    )


def _unpack_import(context: ParserScope, token: Token) -> None:
    if not FEATURE_ALLOW_MODULES:
        msg = "Import feature is not enabled, required to import modules\nModules is still Work-In-Progress, expect possible errors and caveats while using them"
        raise ValueError(msg)
    requested_import_path = _consume_import_raw_path_from_token(context, token)

    # `as` expected
    peeked = context.peek_token()
    named_import_as_name = str(requested_import_path)
    if peeked.type == TokenType.KEYWORD and peeked.value == Keyword.AS:
        context.advance_token()  # consume `as`
        as_name_token = context.next_token()
        assert isinstance(as_name_token.value, str)
        assert as_name_token.type in (TokenType.IDENTIFIER, TokenType.STRING)
        named_import_as_name = as_name_token.value

    if requested_import_path.resolve(strict=False) == context.path:
        msg = f"Tried to import self at {context.path}"
        raise ValueError(msg)

    context.on_import_request(named_import_as_name, requested_import_path)


def _consume_import_raw_path_from_token(
    context: ParserScope,
    include_token: Token,
) -> Path:
    """Consume include path from `include` construction."""
    assert include_token.type == TokenType.KEYWORD
    assert include_token.value == Keyword.MODULE_IMPORT

    import_token = context.next_token()
    if not import_token:
        msg = "no import name"
        raise ValueError(msg)
    if import_token.type not in (TokenType.STRING, TokenType.IDENTIFIER):
        msg = f"import not a string or identifier at {import_token.location}"
        raise ValueError(msg)

    include_path_raw = import_token.value
    assert isinstance(include_path_raw, str)
    return Path(include_path_raw)


def _unpack_inline_raw_assembly(context: ParserScope, token: Token) -> None:
    context.expect_token(TokenType.STRING)
    asm_source = context.next_token()
    assert isinstance(asm_source.value, str)
    context.push_new_operator(
        OperatorType.INLINE_RAW_ASM,
        token=token,
        operand=asm_source.value,
        is_contextual=False,
    )


def _unpack_sizeof_from_token(context: ParserScope, token: Token) -> None:
    sizeof_type = parse_concrete_type_from_tokenizer(
        context,
        allow_inferring_variable_types=True,
    )
    context.push_new_operator(
        OperatorType.PUSH_INTEGER,
        token=token,
        operand=sizeof_type.size_in_bytes,
    )


def _unpack_offset_of_from_token(context: ParserScope, token: Token) -> None:
    struct_type = parse_concrete_type_from_tokenizer(
        context,
        allow_inferring_variable_types=True,
    )
    if not isinstance(struct_type, StructureType):
        msg = f"Expected structure type at {token.location} but got {struct_type}"
        raise TypeError(msg)

    field_token = context.next_token()
    if field_token.type != TokenType.IDENTIFIER:
        msg = f"Expected identifier as field selector for offset-of at {token.location} but got {field_token.type}"
        raise ValueError(msg)

    field_name = field_token.text
    if not struct_type.has_field(field_name):
        msg = (
            f"Field {field_name} does not belongs to {struct_type} at {token.location}"
        )
        # TODO: in this place, and other like this, for generic structures it is possible to pinpoint at original generic type (non concrete one)
        raise ValueError(msg)
    context.push_new_operator(
        OperatorType.PUSH_INTEGER,
        token=token,
        operand=struct_type.get_field_offset(field_name),
    )


def _unpack_function_call_from_token(context: ParserScope, token: Token) -> None:
    name_token = context.next_token()
    if name_token.type != TokenType.IDENTIFIER:
        msg = "expected function name as identifier after `call`"
        raise ValueError(msg)

    owner_module: str | None = None
    if context.peek_token().type == TokenType.DOT:
        # Module level call
        context.advance_token()
        context.expect_token(TokenType.IDENTIFIER)
        module_tok = context.next_token()
        module_tok, name_token = name_token, module_tok
        assert isinstance(module_tok.value, str)
        owner_module = module_tok.value

    name = name_token.text
    function = context.functions.get(name)
    call_spec = FunctionCallOperand(module=owner_module, func=name)

    if name in context.variables:
        variable = context.variables[name]
        assert isinstance(variable.type, FunctionType)
        context.push_new_operator(
            OperatorType.PUSH_VARIABLE_VALUE,
            token=token,
            operand=name,
        )
        context.push_new_operator(
            OperatorType.FUNCTION_CALL_FROM_STACK_POINTER,
            token=token,
            operand=variable.type,
        )
        return

    if function:
        if function.attrs.inline:
            assert not function.attrs.external
            context.expand_from_inline_block(function)
            return
    else:
        assert not context.query_name_holder(name)

    context.push_new_operator(
        OperatorType.FUNCTION_CALL,
        token=token,
        operand=call_spec,
    )


def _unpack_function_definition_from_token(
    context: ParserScope,
    token: Token,
) -> None:
    f_header_def = consume_function_definition(context, token)

    if f_header_def.qualifiers.is_extern:
        function = Function.create_external(
            name=f_header_def.name,
            defined_at=token.location,
            parameters=f_header_def.parameters,
            return_type=f_header_def.return_type,
        )
        function.attrs.no_return = f_header_def.qualifiers.is_no_return
        assert context.module
        function.module = context.module
        context.add_function(function)
        return

    if name_holder := context.query_name_holder(f_header_def.name):
        raise GeneralNameHolderConflictError(
            conflicting_holder=f"Function '{f_header_def.name}' at {token.location}",
            name_holder=name_holder,
        )

    new_context = _new_function_scope(context, token, f_header_def.parameters)

    if f_header_def.qualifiers.is_inline:
        assert not new_context.variables, "Inline functions cannot have local variables"
        assert not f_header_def.qualifiers.is_public, (
            f"Inline functions is always internal private - cannot do public ({token.location})"
        )
        function = Function.create_internal_inline(
            name=f_header_def.name,
            defined_at=token.location,
            operators=new_context.operators,
            return_type=f_header_def.return_type,
            parameters=f_header_def.parameters,
        )
        function.attrs.no_return = f_header_def.qualifiers.is_no_return
        assert context.module
        function.module = context.module
        context.add_function(function)
        return
    if f_header_def.name == context.entry_point_name:  # TODO: Refactor
        f_header_def.qualifiers.is_public = True

    function = Function.create_internal(
        name=f_header_def.name,
        defined_at=token.location,
        operators=new_context.operators,
        variables=new_context.variables,
        parameters=f_header_def.parameters,
        return_type=f_header_def.return_type,
    )

    function.attrs.leaf = new_context.is_leaf_context
    function.attrs.naked = f_header_def.qualifiers.is_naked

    if f_header_def.qualifiers.is_public:
        function.attrs.visibility = Visibility.PUBLIC
    function.attrs.no_return = f_header_def.qualifiers.is_no_return
    assert context.module
    function.module = context.module

    enclosed_new_functions = [
        f for f in new_context.functions.values() if f.name not in context.functions
    ]
    if f_header_def.qualifiers.is_naked:
        if function.variables:
            msg = f"Naked functions cannot have local variables {function.defined_at}"
            raise ValueError(msg)
        if not function.operators:
            msg = f"no instructions inside naked function {function.defined_at}"
            raise ValueError(msg)
        for op in function.operators:
            if op.type != OperatorType.INLINE_RAW_ASM:
                msg = f"Naked functions can only have assembly inlined {function.defined_at}"
                raise ValueError(msg)

    if enclosed_new_functions:
        for enclosure in enclosed_new_functions:
            enclosure.outer_function = function
            _enclosure_generate_native_holder_name(
                context,
                owner=function,
                enclosure=enclosure,
            )
            context.add_function(enclosure)
    context.add_function(function)


def _enclosure_generate_native_holder_name(
    context: ParserScope,
    owner: Function,
    enclosure: Function,
) -> None:
    name = owner.name + "$enclosure"
    enclosure.name = name
    uid = 1
    while context.query_name_holder(enclosure.name):
        name = enclosure.name + f"_{uid}"
        enclosure.name = name
        uid += 1


def _try_unpack_function_call_from_identifier_token(
    context: ParserScope,
    token: Token,
) -> bool:
    assert token.type == TokenType.IDENTIFIER

    name = token.text
    function = context.functions.get(name, None)
    if function:
        if function.attrs.inline:
            context.expand_from_inline_block(function)
            return True
        call_spec = FunctionCallOperand(module=None, func=function)
        context.push_new_operator(
            type=OperatorType.FUNCTION_CALL,
            token=token,
            operand=call_spec,
        )
        return True
    return False
