from collections.abc import Mapping

from libgofra.lexer.keywords import Keyword
from libgofra.lexer.tokens import Token, TokenType
from libgofra.parser._context import ParserContext
from libgofra.parser.errors.unknown_primitive_type import UnknownPrimitiveTypeError
from libgofra.parser.functions.exceptions import ParserFunctionNoNameError
from libgofra.types import Type
from libgofra.types.composite.array import ArrayType
from libgofra.types.composite.function import FunctionType
from libgofra.types.composite.pointer import PointerType
from libgofra.types.generics import (
    GenericArrayType,
    GenericParameter,
    GenericParametrizedType,
    GenericPointerType,
    apply_generic_type_into_concrete,
    get_generic_type_parameters_count,
)


# TODO(@kirillzhosul): deep pointer is not allowed
# TODO(@kirillzhosul): distinguish array-of-pointers and pointer-to-array
# TODO(@kirillzhosul): Type parsing is weird (especially new allow_inferring_variable_types) must be separated in complex-type parsing system ?
def parse_concrete_type_from_tokenizer(
    context: ParserContext,
    *,
    allow_inferring_variable_types: bool = False,
) -> Type:
    """Obtain concrete specialized type from parser/lexer.

    For concrete types only substitution (e.g application) of generic is allowed.
    Cannot define another generic type.
    """
    if context.peek_token().type == TokenType.STAR:
        _ = context.next_token()  # Consume
        return PointerType(
            points_to=parse_concrete_type_from_tokenizer(
                context,
                allow_inferring_variable_types=False,
            ),
        )

    if (
        context.peek_token().type == TokenType.KEYWORD
        and context.peek_token().value == Keyword.FUNCTION
    ):
        _token = context.next_token()
        _, function_params, function_return_type = consume_function_signature(
            context,
            token=_token,
        )

        anonymous_function_params = [t for _, t in function_params]
        return FunctionType(
            return_type=function_return_type,
            parameter_types=anonymous_function_params,
        )
    context.expect_token(TokenType.IDENTIFIER)
    t = context.next_token()

    aggregated_type: Type | GenericParametrizedType | None = context.get_type(t.text)
    if isinstance(aggregated_type, GenericParametrizedType):
        type_params = consume_concrete_generic_type_parameters(context)
        params_required = get_generic_type_parameters_count(aggregated_type)

        if params_required != len(type_params):
            msg = f"Incompatible type params amount for generic type {t.text} at {t.location}. Expected {params_required} but got {len(type_params)}"
            raise ValueError(msg)
        return apply_generic_type_into_concrete(aggregated_type, type_params)

    if not aggregated_type:
        # Unable to get from primitive registry - probably an structure type definition
        aggregated_type = context.get_struct(t.text)

    if allow_inferring_variable_types and not aggregated_type:
        variable = context.search_variable_in_context_parents(t.text)
        if variable:
            aggregated_type = variable.type

    if not aggregated_type:
        raise UnknownPrimitiveTypeError(t.text, t.location)

    if context.peek_token().type == TokenType.LBRACKET:
        _ = context.next_token()  # Consume LBRACKET

        elements = 0
        elements_or_rbracket = context.next_token()

        if elements_or_rbracket.type == TokenType.INTEGER:
            assert isinstance(elements_or_rbracket.value, int)
            elements = elements_or_rbracket.value

            rbracket = context.next_token()
            if rbracket.type != TokenType.RBRACKET:
                msg = f"Expected RBRACKET after array type elements qualifier but got {rbracket.type.name} at {rbracket.location}"
                raise ValueError(msg)
        elif elements_or_rbracket.type != TokenType.RBRACKET:
            msg = f"Expected RBRACKET after array type empty qualifier but got {elements_or_rbracket.type.name} at {elements_or_rbracket.location}"
            raise ValueError(msg)

        aggregated_type = ArrayType(
            element_type=aggregated_type,
            elements_count=elements,
        )

    return aggregated_type


def consume_function_signature(
    context: ParserContext,
    token: Token,
) -> tuple[str, list[tuple[str, Type]], Type]:
    """Consume parser context into function signature assuming given token is `function` keyword.

    Returns function name and signature types (`in` and `out).
    """
    type_contract_out = parse_concrete_type_from_tokenizer(context)

    name_token = context.next_token()

    if not name_token:
        raise ParserFunctionNoNameError(token=token)
    if name_token.type != TokenType.IDENTIFIER:
        msg = f"Expected function name in signature but got {name_token.type.name} at {name_token.location}"
        raise ValueError(msg)
    function_name = name_token.text
    parameters = parse_function_type_parameters(context)

    return function_name, parameters, type_contract_out


def parse_function_type_parameters(context: ParserContext) -> list[tuple[str, Type]]:
    parameters: list[tuple[str, Type]] = []

    if (paren_token := context.next_token()) and paren_token.type != TokenType.LBRACKET:
        msg = f"Expected LBRACKET `[` after function name for parameters but got {paren_token.type.name}"
        raise ValueError(msg, paren_token.location)

    while token := context.peek_token():
        if token.type == TokenType.RBRACKET:
            break
        parameters.append(("", parse_concrete_type_from_tokenizer(context)))
        t = context.peek_token()
        if t.type == TokenType.RBRACKET:
            break
        if t.type == TokenType.IDENTIFIER:
            parameters[-1] = (t.text, parameters[-1][1])
            context.next_token()
            if context.peek_token().type == TokenType.RBRACKET:
                break
        context.expect_token(TokenType.COMMA)
        _ = context.next_token()
    _ = context.next_token()
    return parameters


def parse_generic_type_alias_from_tokenizer(
    context: ParserContext,
    *,
    generic_type_params: Mapping[str, Token],
) -> Type | GenericParametrizedType:
    if generic_type_params:
        for generic_type_param in generic_type_params.values():
            if context.name_is_already_taken(generic_type_param.text):
                msg = f"Generic type param '{generic_type_param.text}' name is already taken by other definition at {generic_type_param.location}"
                raise ValueError(msg)

    if context.peek_token().type == TokenType.STAR:
        context.advance_token()
        points_to = parse_generic_type_alias_from_tokenizer(
            context,
            generic_type_params=generic_type_params,
        )

        if isinstance(points_to, GenericParametrizedType):
            return GenericPointerType(points_to=points_to)

        return PointerType(points_to=points_to)

    if (
        context.peek_token().type == TokenType.KEYWORD
        and context.peek_token().value == Keyword.FUNCTION
    ):
        _token = context.next_token()
        _, function_params, function_return_type = consume_function_signature(
            context,
            token=_token,
        )

        anonymous_function_params = [t for _, t in function_params]
        return FunctionType(
            return_type=function_return_type,
            parameter_types=anonymous_function_params,
        )
    context.expect_token(TokenType.IDENTIFIER)
    token = context.next_token()
    typename = token.text

    base_t: Type | GenericParametrizedType | None
    base_t = context.get_type(typename) or context.get_struct(typename)

    if typename in generic_type_params:
        base_t = GenericParameter(
            name=typename,
            kind=GenericParameter.Kind.TYPE_PARAM,
        )

    if not base_t:
        raise UnknownPrimitiveTypeError(typename, token.location)

    if context.peek_token().type == TokenType.LBRACKET:
        _ = context.next_token()  # Consume LBRACKET

        elements = 0
        elements_or_rbracket = context.next_token()

        if elements_or_rbracket.type == TokenType.INTEGER:
            assert isinstance(elements_or_rbracket.value, int)
            elements = elements_or_rbracket.value
            rbracket = context.next_token()
            if rbracket.type != TokenType.RBRACKET:
                msg = f"Expected RBRACKET after array type elements qualifier but got {rbracket.type.name} at {rbracket.location}"
                raise ValueError(msg)
        elif elements_or_rbracket.type == TokenType.IDENTIFIER:
            identifier = elements_or_rbracket.text
            if identifier not in generic_type_params:
                msg = f"Expected identifier '{identifier}' at {elements_or_rbracket.location} to be an part of generic type params!"
                raise ValueError(msg)
            rbracket = context.next_token()
            if rbracket.type != TokenType.RBRACKET:
                msg = f"Expected RBRACKET after array type elements qualifier but got {rbracket.type.name} at {rbracket.location}"
                raise ValueError(msg)
            return GenericArrayType(
                element_type=base_t,
                element_count=GenericParameter(
                    name=identifier,
                    kind=GenericParameter.Kind.VALUE_PARAM,
                ),
            )
        elif elements_or_rbracket.type != TokenType.RBRACKET:
            msg = f"Expected RBRACKET after array type empty qualifier but got {elements_or_rbracket.type.name}"
            raise ValueError(msg)
        if isinstance(base_t, GenericParametrizedType):
            return GenericArrayType(element_type=base_t, element_count=elements)
        return ArrayType(
            element_type=base_t,
            elements_count=elements,
        )

    return base_t


def consume_concrete_generic_type_parameters(
    context: ParserContext,
) -> Mapping[str, Type | int]:
    generic_type_params: Mapping[str, Type | int] = {}
    if context.peek_token().type == TokenType.LCURLY:
        context.advance_token()
        # Generic type
        generic_type_params = _consume_concrete_generic_type_parameters_list(context)
        context.expect_token(TokenType.RCURLY)
        context.advance_token()

    return generic_type_params


def _consume_concrete_generic_type_parameters_list(
    context: ParserContext,
) -> Mapping[str, Type | int]:
    type_params: Mapping[
        str,
        Type | int,
    ] = {}  # TODO(@kirillzhosul): Named type but also can be value argument (param)
    while token := context.peek_token():
        if token.type == TokenType.RCURLY:
            break
        context.expect_token(TokenType.IDENTIFIER)
        typename_token = context.next_token()

        context.expect_token(TokenType.ASSIGNMENT)
        context.advance_token()

        typename = typename_token.text

        if context.peek_token().type == TokenType.INTEGER:
            tok = context.next_token()
            assert isinstance(tok.value, int)
            type_params[typename] = tok.value
        else:
            type_params[typename] = parse_concrete_type_from_tokenizer(
                context,
                allow_inferring_variable_types=False,
            )

        t = context.peek_token()
        if t.type == TokenType.RCURLY:
            break
        context.expect_token(TokenType.COMMA)
        _ = context.next_token()
    return type_params


def consume_generic_type_parameters(context: ParserContext) -> Mapping[str, Token]:
    """Consume parameters for generic type definition if specified (e.g cursor points at `{`.

    e.g X{T, N}
    Otherwise returns empty type parameters.
    """
    generic_type_params: Mapping[str, Token] = {}
    if context.peek_token().type == TokenType.LCURLY:
        context.advance_token()
        # Generic type
        generic_type_params = _consume_generic_type_parameters_list(context)
        context.expect_token(TokenType.RCURLY)
        context.advance_token()

    return generic_type_params


def _consume_generic_type_parameters_list(
    context: ParserContext,
) -> Mapping[str, Token]:
    """Read `consume_generic_type_parameters`."""
    type_params: Mapping[str, Token] = {}
    while token := context.peek_token():
        if token.type == TokenType.RCURLY:
            break
        context.expect_token(TokenType.IDENTIFIER)
        t_token = context.next_token()
        type_params[t_token.text] = t_token
        t = context.peek_token()
        if t.type == TokenType.RCURLY:
            break
        context.expect_token(TokenType.COMMA)
        _ = context.next_token()
    return type_params
