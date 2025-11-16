from typing import cast

from gofra.feature_flags import FEATURE_RUNTIME_ARRAY_OOB_CHECKS
from gofra.hir.operator import OperatorType
from gofra.hir.variable import (
    Variable,
    VariableIntArrayInitializerValue,
    VariableScopeClass,
    VariableStorageClass,
    VariableStringInitializerValue,
)
from gofra.lexer.keywords import Keyword
from gofra.lexer.tokens import Token, TokenType
from gofra.parser._context import ParserContext
from gofra.parser.errors.cannot_infer_var_type_from_empty_array_initializer import (
    CannotInferVariableTypeFromEmptyArrayInitializerError,
)
from gofra.parser.errors.cannot_infer_var_type_from_initializer import (
    CannotInferVariableTypeFromInitializerError,
)
from gofra.parser.errors.constant_variable_requires_intializer import (
    ConstantVariableRequiresInitializerError,
)
from gofra.parser.errors.type_has_no_compile_time_initializer import (
    TypeHasNoCompileTimeInitializerParserError,
)
from gofra.parser.errors.unknown_field_accessor_struct_field import (
    UnknownFieldAccessorStructFieldError,
)
from gofra.parser.errors.variable_with_void_type import (
    VariableCannotHasVoidTypeParserError,
)
from gofra.parser.exceptions import ParserVariableNameAlreadyDefinedAsVariableError
from gofra.parser.types import (
    parse_concrete_type_from_tokenizer,
)
from gofra.types._base import Type
from gofra.types.composite.array import ArrayType
from gofra.types.composite.pointer import PointerType
from gofra.types.composite.string import StringType
from gofra.types.composite.structure import StructureType
from gofra.types.primitive.boolean import BoolType
from gofra.types.primitive.character import CharType
from gofra.types.primitive.integers import I64Type
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
        initial_value, var_t = _consume_variable_initializer(
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


def try_push_variable_reference(context: ParserContext, token: Token) -> bool:
    assert token.type == TokenType.IDENTIFIER

    varname = token.text

    is_reference = False
    array_index_at: int | Variable[Type] | None = None
    struct_field_accessor = None

    if varname.startswith("&"):
        is_reference = True
        varname = varname.removeprefix("&")

    if context.peek_token().type == TokenType.LBRACKET:
        _ = context.next_token()  # Consume LBRACKET

        elements_token = context.next_token()
        if elements_token.type not in (TokenType.INTEGER, TokenType.IDENTIFIER):
            msg = (
                f"Expected array index inside of [], but got {elements_token.type.name}"
            )
            raise ValueError(msg)

        rbracket = context.next_token()
        if rbracket.type != TokenType.RBRACKET:
            msg = f"Expected RBRACKET after array index element qualifier but got {rbracket.type.name}"
            raise ValueError(msg)

        if elements_token.type == TokenType.INTEGER:
            # Simple integer array access
            assert isinstance(elements_token.value, int)
            array_index_at = elements_token.value
        else:
            # Variable index access
            assert isinstance(elements_token.value, str)
            array_index_at = context.search_variable_in_context_parents(
                elements_token.value,
            )
            if array_index_at is None:
                msg = f"Expected known VARIABLE at {token.location} as array-index-of but unknown variable '{elements_token.value}'"
                raise ValueError(msg)

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

    variable = context.search_variable_in_context_parents(varname)
    if not variable:
        return False

    if (
        variable.is_constant
        and variable.type.size_in_bytes <= 8
        and not is_reference
        and not struct_field_accessor
        and array_index_at is None
        and isinstance(variable.type, (BoolType, I64Type, CharType))
    ):
        # Simple unwrapping for constants
        assert isinstance(variable.initial_value, int)
        context.push_new_operator(
            type=OperatorType.PUSH_INTEGER,
            token=token,
            operand=variable.initial_value,
        )
        return True

    context.push_new_operator(
        type=OperatorType.PUSH_VARIABLE_ADDRESS,
        token=token,
        operand=varname,
    )

    if struct_field_accessor:
        if not isinstance(variable.type, StructureType) and not isinstance(
            variable.type,
            PointerType,
        ):
            msg = f"cannot get field-offset-of (e.g .field) for non-structure or pointers to structure types at {token.location}."
            raise ValueError(msg)

        struct = variable.type
        if isinstance(variable.type, PointerType) and isinstance(
            variable.type.points_to,
            StructureType,
        ):
            # If we have struct field accessor for analogue of `->` (E.g *struct)
            # we must dereference that struct pointer and deal with direct pointer to it
            # struct is remapped to pointer holding that type
            context.push_new_operator(
                type=OperatorType.MEMORY_VARIABLE_READ,
                token=token,
            )
            struct = variable.type.points_to
        assert isinstance(struct, StructureType)

        field = struct_field_accessor.text
        if field not in struct.fields:
            raise UnknownFieldAccessorStructFieldError(field, token.location, struct)

        context.push_new_operator(
            type=OperatorType.STRUCT_FIELD_OFFSET,
            token=token,
            operand=f"{struct.name}.{field}",
        )

    if array_index_at is not None:
        if not isinstance(variable.type, ArrayType):
            msg = (
                f"cannot get index-of (e.g []) for non-array types. at {token.location}"
            )
            raise ValueError(msg)

        if isinstance(array_index_at, Variable):
            var = array_index_at
            if not isinstance(var.type, (I64Type, CharType)):
                msg = f"Non I64/char type cannot be used as index at {token.location}!"
                raise TypeError(msg)
            if var.is_constant and isinstance(var.initial_value, int):
                array_index_at = var.initial_value

        if isinstance(array_index_at, int):
            # Access by integer (direct int or expanded from constant)
            # Compile-time OOB checks
            if array_index_at < 0:
                msg = "Negative indexing inside arrays is prohibited"
                raise ValueError(msg)

            if variable.type.is_index_oob(array_index_at):
                msg = f"OOB (out-of-bounds) for array access `{token.text}` at {token.location}, array has {variable.type.elements_count} elements but accessed element {array_index_at} (may be expanded from constant)"
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
        else:
            # Access by non-constant variable
            context.push_new_operator(
                OperatorType.PUSH_INTEGER,
                token,
                operand=variable.type.element_type.size_in_bytes,
            )
            context.push_new_operator(
                OperatorType.PUSH_VARIABLE_ADDRESS,
                token,
                operand=array_index_at.name,
            )
            context.push_new_operator(OperatorType.MEMORY_VARIABLE_READ, token)
            if FEATURE_RUNTIME_ARRAY_OOB_CHECKS:
                assert isinstance(array_index_at.type, (I64Type, CharType))
                array_index_at = cast("Variable[I64Type]", array_index_at)
                _emit_runtime_oob_check(
                    context,
                    token,
                    array_index_at,
                    variable.type.elements_count,
                )
            context.push_new_operator(OperatorType.ARITHMETIC_MULTIPLY, token)
            context.push_new_operator(OperatorType.ARITHMETIC_PLUS, token)

    if is_reference and variable.is_constant:
        msg = f"Tried to get reference of constant variable {variable.name} at {token.location}"
        raise ValueError(msg)
    if not is_reference:
        if variable.type.size_in_bytes > 8 and not (
            array_index_at is not None or struct_field_accessor
        ):
            msg = f"Cannot load variable {variable.name} of type {variable.type} as it has size {variable.type.size_in_bytes} in bytes (stack-cell-overflow) at {token.location}"
            raise ValueError(msg)
        context.push_new_operator(
            type=OperatorType.MEMORY_VARIABLE_READ,
            token=token,
        )
    return True


def _emit_runtime_oob_check(
    context: ParserContext,
    token: Token,
    index_var: Variable[I64Type],
    elements_const: int,
) -> None:
    """Push operators to perform OOB check at runtime.

    TODO(@kirillzhosul): Must be reworked into runtime lib?:
    Possibly introduce runtime include library, should requires via something like `require_runtime_function`
    """
    panic_msg = "Runtime OOB error: tried to access array with out-of-bounds index, step into debugger for help!\\n"
    context.push_new_operator(
        OperatorType.PUSH_VARIABLE_ADDRESS,
        token,
        operand=index_var.name,
    )
    context.push_new_operator(OperatorType.MEMORY_VARIABLE_READ, token)
    context.push_new_operator(
        OperatorType.PUSH_INTEGER,
        operand=elements_const,
        token=token,
    )
    context.push_new_operator(OperatorType.COMPARE_GREATER_EQUALS, token)
    context.push_new_operator(OperatorType.CONDITIONAL_IF, token, is_contextual=True)
    context.push_new_operator(
        OperatorType.PUSH_STRING,
        operand=panic_msg,
        token=Token(
            type=TokenType.STRING,
            text=f'"{panic_msg}"',
            value=panic_msg,
            location=token.location,
        ),
    )
    if "eprint_fatal" not in context.functions:
        msg = "Cannot do FEATURE_RUNTIME_ARRAY_OOB_CHECKS unless stdlib (`eprint_fatal`) is available for panic"
        raise ValueError(msg)
    context.push_new_operator(
        OperatorType.FUNCTION_CALL,
        token=token,
        operand="eprint_fatal",
    )
    context.push_new_operator(OperatorType.CONDITIONAL_END, token=token)
    _, if_op, _ = context.pop_context_stack()
    if_op.jumps_to_operator_idx = context.current_operator - 1


def _consume_variable_initializer(
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
