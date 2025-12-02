from typing import TYPE_CHECKING

from gofra.hir.initializer import (
    T_AnyVariableInitializer,
    VariableIntArrayInitializerValue,
    VariableIntFieldedStructureInitializerValue,
    VariableStringPtrArrayInitializerValue,
    VariableStringPtrInitializerValue,
)
from gofra.lexer.tokens import Token, TokenType
from gofra.parser._context import ParserContext
from gofra.parser.errors.type_has_no_compile_time_initializer import (
    TypeHasNoCompileTimeInitializerParserError,
)
from gofra.parser.variable_type_inference import infer_type_from_initializer
from gofra.types._base import Type
from gofra.types.composite.array import ArrayType
from gofra.types.composite.pointer import PointerType
from gofra.types.composite.string import StringType
from gofra.types.composite.structure import StructureType
from gofra.types.primitive.boolean import BoolType
from gofra.types.primitive.character import CharType
from gofra.types.primitive.integers import I64Type

if TYPE_CHECKING:
    from collections.abc import Mapping


def consume_variable_initializer(
    context: ParserContext,
    var_t: Type | None,
    varname_token: Token,
) -> tuple[T_AnyVariableInitializer, Type]:
    if var_t is None:
        var_t = infer_type_from_initializer(context, varname_token)

    match var_t:
        case PointerType(points_to=StringType()) | StringType():
            return _consume_string_literal_initializer(var_t, context), var_t
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

            int_values: list[int] = []
            while True:
                if context.peek_token().type == TokenType.RBRACKET:
                    _ = context.next_token()
                    break

                context.expect_token(TokenType.INTEGER)
                value_token = context.next_token()
                assert isinstance(value_token.value, int)
                element_value = value_token.value
                int_values.append(element_value)
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
                var_t.elements_count = len(int_values)

            if len(int_values) > var_t.elements_count:
                msg = f"Array initializer got {len(int_values)} elements at {varname_token.location}, but array size is {var_t.elements_count} which overflows array!"
                raise ValueError(msg)
            # This allows not all array to be initialized and its ok
            return VariableIntArrayInitializerValue(
                default=0,
                values=int_values,
            ), var_t
        case ArrayType(element_type=PointerType(points_to=StringType())):
            # TODO(@kirillzhosul): Must be refactor in general array initializer logic
            context.expect_token(TokenType.LBRACKET)
            context.next_token()

            str_values: list[str] = []
            while True:
                if context.peek_token().type == TokenType.RBRACKET:
                    _ = context.next_token()
                    break

                context.expect_token(TokenType.STRING)
                str_token = context.next_token()
                assert isinstance(str_token.value, str)
                string_raw = str(str_token.text[1:-1])
                str_values.append(string_raw)

                if context.peek_token().type == TokenType.RBRACKET:
                    _ = context.next_token()
                    break
                context.expect_token(TokenType.COMMA)
                _ = context.next_token()

            # TODO(@kirillzhosul): General semantic problem? t[0] means unfinished array definition and allows this to pass
            if var_t.elements_count == 0:
                var_t.elements_count = len(str_values)

            if len(str_values) > var_t.elements_count:
                msg = f"Array initializer got {len(str_values)} elements at {varname_token.location}, but array size is {var_t.elements_count} which overflows array!"
                raise ValueError(msg)
            # This allows not all array to be initialized and its ok
            return VariableStringPtrArrayInitializerValue(
                default=0,
                values=str_values,
            ), var_t

        case StructureType():
            return _consume_structure_initializer(var_t, context, varname_token), var_t
        case _:
            raise TypeHasNoCompileTimeInitializerParserError(
                type_with_no_initializer=var_t,
                varname=varname_token.text,
                at=varname_token.location,
            )


def _consume_string_literal_initializer(
    t: PointerType | StringType,
    context: ParserContext,
) -> VariableStringPtrInitializerValue:
    string_token = context.next_token()
    if string_token.type != TokenType.STRING:
        # TODO(@kirillzhosul): Proper error message
        msg = f"Expected STRING for initializer (type {t}), but got {string_token.type.name} at {string_token.location}"
        raise ValueError(msg)
    string_raw = str(string_token.text[1:-1])

    match t:
        case PointerType(points_to=StringType()):
            return VariableStringPtrInitializerValue(string=string_raw)
        case StringType():
            # TODO(@kirillzhosul): Allow unfolded string initializer
            msg = "Unfolded string initializer is not implemented yet! (please use *string, not string)"
            raise NotImplementedError(msg)
        case _:
            msg = f"Unexpected type in {_consume_string_literal_initializer.__name__}, probably an bug in toolchain"
            raise ValueError(msg)


def _consume_structure_initializer(
    var_t: StructureType,
    context: ParserContext,
    varname_token: Token,
) -> VariableIntFieldedStructureInitializerValue:
    context.expect_token(TokenType.LCURLY)
    context.advance_token()

    # TODO(@kirillzhosul): Same as other similar blocks - requires whitespace by lexer ERROR
    int_fields: Mapping[str, int] = {}
    while token := context.peek_token():
        if token.type == TokenType.RCURLY:
            context.advance_token()
            break
        context.expect_token(TokenType.IDENTIFIER)
        field_name_token = context.next_token()
        field_name = field_name_token.text

        context.expect_token(TokenType.ASSIGNMENT)
        context.advance_token()

        if context.peek_token().type == TokenType.INTEGER:
            tok = context.next_token()
            assert isinstance(tok.value, int)
            int_fields[field_name] = tok.value
        else:
            msg = f"Only integer literal structure fields initializer are allowed for now at {context.peek_token().location}"
            raise ValueError(msg)

        t = context.peek_token()
        if t.type == TokenType.RCURLY:
            context.advance_token()
            break
        context.expect_token(TokenType.COMMA)
        _ = context.next_token()

    abnormals_fields = set(int_fields.keys()).difference(var_t.fields)
    if abnormals_fields:
        msg = f"Abnormal field(s) for structure initializer: {abnormals_fields} at {varname_token.location}"
        raise ValueError(msg)

    missing_fields = set(var_t.fields).difference(int_fields.keys())
    if missing_fields:
        msg = f"Missing field(s) for structure initializer: {missing_fields} at {varname_token.location}"
        raise ValueError(msg)

    return VariableIntFieldedStructureInitializerValue(values=int_fields)


def _validate_initial_numeric_value_fits_type(
    t: Type,
    value: int,
    from_token: Token,
) -> None:
    """Treat any given type as LHS value for initializer assignment and validate is given numerical value fits size of that type."""
    if value.bit_count() <= (t.size_in_bytes * 8):
        return
    msg = f"Default value is to big for that type ({t}) at {from_token.location} ["
    raise ValueError(msg)
