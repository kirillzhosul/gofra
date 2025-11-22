from gofra.hir.variable import (
    Variable,
    VariableScopeClass,
    VariableStorageClass,
)
from gofra.lexer.keywords import Keyword
from gofra.lexer.tokens import Token, TokenType
from gofra.parser._context import ParserContext
from gofra.parser.errors.constant_variable_requires_initializer import (
    ConstantVariableRequiresInitializerError,
)
from gofra.parser.errors.variable_with_void_type import (
    VariableCannotHasVoidTypeParserError,
)
from gofra.parser.exceptions import ParserVariableNameAlreadyDefinedAsVariableError
from gofra.parser.type_parser import (
    parse_concrete_type_from_tokenizer,
)
from gofra.parser.variable_initializer import consume_variable_initializer
from gofra.types.primitive.void import VoidType


def _consume_variable_modifier_is_const(
    context: ParserContext,
    begin_token: Token,
) -> bool:
    """Consume modifiers for *definition* (e.g constant or variable* from token that describes start of definition (any modifier or specifier).

    Next token must be an identifier holding definition name.

    Allowed forms: `const x`, `const var x`, `var x`
    """
    assert begin_token.type == TokenType.KEYWORD, "Expected keyword (e.g const / var)"

    if begin_token.value != Keyword.CONST:
        return False

    peeked = context.peek_token()
    if peeked.type == TokenType.KEYWORD and peeked.value == Keyword.VARIABLE_DEFINE:
        context.advance_token()
        # Skip `var` token, if next is non an identifier - caller must emit an error by itself

    return True


def _validate_variable_redefinition(
    context: ParserContext,
    name: str,
    token: Token,
) -> None:
    if name in context.variables:
        raise ParserVariableNameAlreadyDefinedAsVariableError(
            token=token,
            name=name,
        )

    if context.name_is_already_taken(name):
        previous_def = context.search_variable_in_context_parents(name)
        msg = f"Variable name {name} at {token.location} is already taken by other definition within context parents at {previous_def.defined_at if previous_def else 'unknown location'}"
        raise ValueError(msg)


def unpack_variable_definition_from_token(
    context: ParserContext,
    token: Token,
) -> None:
    assert token.type == TokenType.KEYWORD
    modifier_is_const = _consume_variable_modifier_is_const(context, token)

    varname_token = context.next_token()
    if varname_token.type != TokenType.IDENTIFIER:
        msg = f"Expected variable name after variable keyword but got {varname_token.type.name} at {varname_token.location}"
        raise ValueError(msg)
    assert isinstance(varname_token.value, str)

    varname = varname_token.text
    _validate_variable_redefinition(context, varname, varname_token)

    var_t = None  # Infer by default
    if context.peek_token().type == TokenType.ASSIGNMENT:
        pass
    else:
        var_t = parse_concrete_type_from_tokenizer(context)

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

    initial_value = None

    if context.peek_token().type == TokenType.ASSIGNMENT:
        _ = context.next_token()  # consume =

        # Parse value and infer type from that
        # `var_t` can be changed if it is inferred type
        # Or initializer modifies type (e.g incomplete array type)
        initial_value, var_t = consume_variable_initializer(
            context,
            var_t,
            varname_token=varname_token,
        )
    elif modifier_is_const:
        raise ConstantVariableRequiresInitializerError(varname, token.location)

    if isinstance(var_t, VoidType):
        raise VariableCannotHasVoidTypeParserError(
            varname=varname,
            defined_at=varname_token,
        )

    if var_t and var_t.size_in_bytes == 0:
        msg = f"Variable {varname} defined at {varname_token.location} has type {var_t}, which has zero byte size! Possible alternative to void, which is prohibited"
        raise TypeError(msg)

    assert var_t, "Must emit infer error"
    context.variables[varname] = Variable(
        name=varname,
        type=var_t,
        defined_at=varname_token.location,
        scope_class=scope_class,
        storage_class=storage_class,
        initial_value=initial_value,
        is_constant=modifier_is_const,
    )
