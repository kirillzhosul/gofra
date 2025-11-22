from gofra.hir.variable import (
    VariableIntArrayInitializerValue,
    VariableStringInitializerValue,
)
from gofra.lexer.tokens import Token, TokenType
from gofra.parser._context import ParserContext
from gofra.parser.errors.cannot_infer_var_type_from_empty_array_initializer import (
    CannotInferVariableTypeFromEmptyArrayInitializerError,
)
from gofra.parser.errors.cannot_infer_var_type_from_initializer import (
    CannotInferVariableTypeFromInitializerError,
)
from gofra.parser.errors.type_has_no_compile_time_initializer import (
    TypeHasNoCompileTimeInitializerParserError,
)
from gofra.types._base import Type
from gofra.types.composite.array import ArrayType
from gofra.types.composite.pointer import PointerType
from gofra.types.composite.string import StringType
from gofra.types.primitive.boolean import BoolType
from gofra.types.primitive.character import CharType
from gofra.types.primitive.integers import I64Type


def consume_variable_initializer(
    context: ParserContext,
    var_t: Type | None,
    varname_token: Token,
) -> tuple[
    int | VariableIntArrayInitializerValue | VariableStringInitializerValue,
    Type,
]:
    if var_t is None:
        var_t = _infer_auto_variable_type_from_initializer(context, varname_token)

    match var_t:
        case PointerType(points_to=StringType()):
            string_token = context.next_token()
            if string_token.type != TokenType.STRING:
                msg = f"Expected STRING for initializer (type {var_t}), but got {string_token.type.name} at {string_token.location}"
                raise ValueError(msg)
            string_raw = str(string_token.text[1:-1])
            return VariableStringInitializerValue(string=string_raw), var_t
        case I64Type() | CharType():
            value_token = context.next_token()
            if value_token.type not in (TokenType.INTEGER, TokenType.CHARACTER):
                msg = f"Expected INTEGER or CHARACTER for initializer (type {var_t}), but got {value_token.type.name} at {value_token.location}"
                raise ValueError(msg)

            assert isinstance(value_token.value, int)
            initial_value = value_token.value

            _validate_initial_numeric_value_fits_type(var_t, initial_value, value_token)
            return initial_value, var_t
        case BoolType():
            value_token = context.next_token()
            if value_token.type != TokenType.INTEGER:
                msg = f"Expected INTEGER for initializer (type {var_t}), but got {value_token.type.name} at {value_token.location}"
                raise ValueError(msg)

            assert isinstance(value_token.value, int)
            initial_value = value_token.value

            if initial_value not in (0, 1):
                msg = f"Default value for boolean must be in two states: 0 or 1, but got {initial_value} as initial value at {value_token.location}"
                raise ValueError(msg)
            return initial_value, var_t
        case ArrayType(element_type=I64Type()):
            context.expect_token(TokenType.LBRACKET)
            context.next_token()

            values: list[int] = []
            while True:
                if context.peek_token().type == TokenType.RBRACKET:
                    _ = context.next_token()
                    break

                context.expect_token(TokenType.INTEGER)
                value_token = context.next_token()
                assert isinstance(value_token.value, int)
                element_value = value_token.value
                values.append(element_value)
                _validate_initial_numeric_value_fits_type(
                    var_t.element_type,
                    element_value,
                    value_token,
                )
                if context.peek_token().type == TokenType.RBRACKET:
                    _ = context.next_token()
                    break
                context.expect_token(TokenType.COMMA)
                _ = context.next_token()

            # TODO(@kirillzhosul): General semantic problem? t[0] means unfinished array definition and allows this to pass
            if var_t.elements_count == 0:
                var_t.elements_count = len(values)

            if len(values) > var_t.elements_count:
                msg = f"Array initializer got {len(values)} elements at {varname_token.location}, but array size is {var_t.elements_count} which overflows array!"
                raise ValueError(msg)
            # This allows not all array to be initialized and its ok
            return VariableIntArrayInitializerValue(
                default=0,
                values=values,
            ), var_t
        case _:
            raise TypeHasNoCompileTimeInitializerParserError(
                type_with_no_initializer=var_t,
                varname=varname_token.text,
                at=varname_token.location,
            )


def _validate_initial_numeric_value_fits_type(
    t: Type,
    value: int,
    from_token: Token,
) -> None:
    if value.bit_count() > t.size_in_bytes * 8:
        msg = f"Default value is to big for that type ({t}) at {from_token.location}"
        raise ValueError(msg)


def _infer_auto_variable_type_from_initializer(
    context: ParserContext,
    varname_token: Token,
) -> Type:
    if context.peek_token().type == TokenType.INTEGER:
        return I64Type()

    if context.peek_token().type == TokenType.CHARACTER:
        return CharType()

    if context.peek_token().type == TokenType.STRING:
        return PointerType(points_to=StringType())

    if context.peek_token().type == TokenType.LBRACKET:
        lbracket = context.next_token()
        if context.peek_token().type == TokenType.RBRACKET:
            raise CannotInferVariableTypeFromEmptyArrayInitializerError(
                varname_token.text,
                varname_token.location,
            )

        if context.peek_token().type == TokenType.INTEGER:
            context.push_token_back_upfront_peeked(lbracket)
            return ArrayType(
                element_type=I64Type(),
                elements_count=0,
            )  # Incomplete array definition

        context.push_token_back_upfront_peeked(lbracket)

    raise CannotInferVariableTypeFromInitializerError(
        varname_token.text,
        varname_token.location,
    )
