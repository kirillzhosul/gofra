from dataclasses import dataclass
from typing import cast

from libgofra.hir.operator import OperatorType
from libgofra.hir.variable import (
    Variable,
)
from libgofra.lexer.tokens import Token, TokenType
from libgofra.parser._context import ParserContext
from libgofra.parser.errors.static_array_out_of_bounds import ArrayOutOfBoundsError
from libgofra.parser.errors.unknown_field_accessor_struct_field import (
    UnknownFieldAccessorStructFieldError,
)
from libgofra.parser.runtime_oob_check import emit_runtime_hir_oob_check
from libgofra.types._base import Type
from libgofra.types.composite.array import ArrayType
from libgofra.types.composite.pointer import PointerType
from libgofra.types.composite.structure import StructureType
from libgofra.types.primitive.character import CharType
from libgofra.types.primitive.integers import I64Type


@dataclass
class _VariableAccessorExpr:
    variable: Variable[Type]
    is_reference: bool
    array_index_at: int | Variable[Type] | None
    struct_field_accessor: Token | None

    def is_direct_expr(self) -> bool:
        return (
            not self.is_reference
            and not self.struct_field_accessor
            and self.array_index_at is None
        )


def try_push_variable_reference(context: ParserContext, token: Token) -> bool:
    if not (expr := _resolve_variable_expr(context, token)):
        return False

    if _try_unwind_constant(context, token, expr):
        return True

    variable = expr.variable
    if expr.is_reference and variable.is_constant:
        # Probably we must allow reference but mark them as immutable memory locations
        # this was easiest solution at that time
        msg = f"Tried to get reference of constant variable {variable.name} at {token.location}"
        raise ValueError(msg)

    if (
        not expr.is_reference
        and variable.type.size_in_bytes > 8
        and not (expr.array_index_at is not None or expr.struct_field_accessor)
    ):
        msg = f"Cannot load variable {variable.name} of type {variable.type} as it has size {variable.type.size_in_bytes} in bytes (stack-cell-overflow) at {token.location}"
        raise ValueError(msg)

    if (
        expr.struct_field_accessor
        or expr.array_index_at is not None
        or expr.is_reference
    ):
        context.push_new_operator(
            type=OperatorType.PUSH_VARIABLE_ADDRESS,
            token=token,
            operand=variable.name,
        )
    else:
        context.push_new_operator(
            type=OperatorType.PUSH_VARIABLE_VALUE,
            token=token,
            operand=variable.name,
        )
        return True

    if expr.struct_field_accessor:
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

        field = expr.struct_field_accessor.text
        if not struct.has_field(field):
            raise UnknownFieldAccessorStructFieldError(field, token.location, struct)

        context.push_new_operator(
            type=OperatorType.STRUCT_FIELD_OFFSET,
            token=token,
            operand=(struct, field),
        )

    if expr.array_index_at is not None:
        if not isinstance(variable.type, ArrayType):
            msg = (
                f"cannot get index-of (e.g []) for non-array types. at {token.location}"
            )
            raise ValueError(msg)

        if isinstance(expr.array_index_at, Variable):
            var = expr.array_index_at
            if not isinstance(var.type, (I64Type, CharType)):
                msg = f"Non I64/char type cannot be used as index at {token.location}!"
                raise TypeError(msg)
            if var.is_constant and isinstance(var.initial_value, int):
                array_index_at = var.initial_value

        if isinstance(expr.array_index_at, int):
            # Access by integer (direct int or expanded from constant)
            # Compile-time OOB checks
            if variable.type.is_index_oob(expr.array_index_at):
                raise ArrayOutOfBoundsError(
                    at=token.location,
                    variable=cast("Variable[ArrayType]", variable),
                    array_index_at=expr.array_index_at,
                )

            shift_in_bytes = variable.type.get_index_offset(expr.array_index_at)
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
                OperatorType.PUSH_VARIABLE_VALUE,
                token,
                operand=expr.array_index_at.name,
            )
            if context.rt_array_oob_check:
                assert isinstance(expr.array_index_at.type, (I64Type, CharType))
                array_index_at = cast("Variable[I64Type]", expr.array_index_at)
                emit_runtime_hir_oob_check(
                    context,
                    token,
                    array_index_at,
                    variable.type.elements_count,
                )
            context.push_new_operator(OperatorType.ARITHMETIC_MULTIPLY, token)
            context.push_new_operator(OperatorType.ARITHMETIC_PLUS, token)

    if not expr.is_reference:
        context.push_new_operator(
            type=OperatorType.MEMORY_VARIABLE_READ,
            token=token,
        )
    return True


def _try_unwind_constant(
    context: ParserContext,
    token: Token,
    expr: _VariableAccessorExpr,
) -> bool:
    if (
        expr.variable.is_constant
        and expr.variable.type.size_in_bytes <= 8
        and expr.is_direct_expr()
        and expr.variable.is_primitive_type
    ):
        # Simple unwrapping for constants
        assert isinstance(expr.variable.initial_value, int)
        context.push_new_operator(
            type=OperatorType.PUSH_INTEGER,
            token=token,
            operand=expr.variable.initial_value,
        )
        return True
    return False


def _resolve_variable_expr(
    context: ParserContext,
    token: Token,
) -> _VariableAccessorExpr | None:
    assert token.type == TokenType.IDENTIFIER
    varname = token.text

    is_reference = False
    if varname.startswith("&"):
        is_reference = True
        varname = varname.removeprefix("&")

    variable = context.search_variable_in_context_parents(varname)
    if not variable:
        return None

    expr = _VariableAccessorExpr(
        variable=variable,
        is_reference=is_reference,
        struct_field_accessor=None,
        array_index_at=None,
    )

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
            expr.array_index_at = elements_token.value
        else:
            # Variable index access
            assert isinstance(elements_token.value, str)
            expr.array_index_at = context.search_variable_in_context_parents(
                elements_token.value,
            )
            if expr.array_index_at is None:
                msg = f"Expected known VARIABLE at {token.location} as array-index-of but unknown variable '{elements_token.value}'"
                raise ValueError(msg)

    accessor_token = context.peek_token()
    if (
        accessor_token.type == TokenType.DOT
        and not accessor_token.has_trailing_whitespace
    ):
        _ = context.next_token()  # Consume DOT
        if expr.array_index_at is not None:
            msg = "Referencing an field from an struct within array accessor is not implemented yet."
            raise NotImplementedError(msg)
        expr.struct_field_accessor = context.next_token()
        if expr.struct_field_accessor.type != TokenType.IDENTIFIER:
            msg = f"Expected struct field accessor to be an identifier, but got {expr.struct_field_accessor.type.name}"
            raise ValueError(msg)

    return expr
