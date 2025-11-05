from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from gofra.consts import GOFRA_ENTRY_POINT
from gofra.hir.operator import OperatorType
from gofra.parser.exceptions import (
    ParserEntryPointFunctionModifiersError,
    ParserNoEntryFunctionError,
)
from gofra.typecheck.errors.entry_point_parameters_mismatch import (
    EntryPointParametersMismatchTypecheckError,
)
from gofra.typecheck.errors.entry_point_return_type_mismatch import (
    EntryPointReturnTypeMismatchTypecheckError,
)
from gofra.typecheck.errors.return_value_missing import ReturnValueMissingTypecheckError
from gofra.types import Type
from gofra.types.comparison import is_types_same
from gofra.types.composite.array import ArrayType
from gofra.types.composite.pointer import PointerType
from gofra.types.composite.structure import StructureType
from gofra.types.primitive.boolean import BoolType
from gofra.types.primitive.character import CharType
from gofra.types.primitive.integers import I64Type

from ._context import TypecheckContext
from .exceptions import (
    TypecheckBlockStackMismatchError,
    TypecheckFunctionTypeContractOutViolatedError,
    TypecheckInvalidBinaryMathArithmeticsError,
    TypecheckInvalidPointerArithmeticsError,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from gofra.hir.function import Function
    from gofra.hir.module import Module
    from gofra.hir.operator import Operator


# TODO(@kirillzhosul): Probably be something like an debug flag
# Traces each operation on stack to search bugs in typechecker
DEBUG_TRACE_TYPESTACK = False


def validate_type_safety(
    module: Module,
) -> None:
    """Validate type safety of an program by type checking all given functions."""
    if GOFRA_ENTRY_POINT not in module.functions:
        raise ParserNoEntryFunctionError

    # TODO(@kirillzhosul): these parser errors comes from legacy entry point validation, must be reworked later - https://github.com/kirillzhosul/gofra/issues/28
    entry_point = module.functions[GOFRA_ENTRY_POINT]
    if entry_point.is_external or entry_point.is_inline:
        raise ParserEntryPointFunctionModifiersError

    if entry_point.has_return_value() and not isinstance(
        entry_point.return_type,
        I64Type,
    ):
        raise EntryPointReturnTypeMismatchTypecheckError(
            return_type=entry_point.return_type,
        )

    if entry_point.parameters:
        raise EntryPointParametersMismatchTypecheckError(
            parameters=entry_point.parameters,
        )

    for function in (*module.functions.values(), entry_point):
        if function.is_external:
            continue
        validate_function_type_safety(
            function=function,
            module=module,
        )


def validate_function_type_safety(
    function: Function,
    module: Module,
) -> None:
    """Emulate and validate function type safety inside."""
    emulated_type_stack = emulate_type_stack_for_operators(
        operators=function.operators,
        module=module,
        initial_type_stack=list(function.parameters),
        current_function=function,
    )

    # TODO(@kirillzhosul): Probably this should be refactored due to overall new complexity of an `ANY` and coercion.

    if not function.has_return_value() and emulated_type_stack:
        # function must not return any
        raise TypecheckFunctionTypeContractOutViolatedError(
            function=function,
            type_stack=list(emulated_type_stack),
        )
    if function.has_return_value():
        if len(emulated_type_stack) == 0:
            raise ReturnValueMissingTypecheckError(owner=function)

        if len(emulated_type_stack) > 1:
            msg = f"Ambiguous stack size at function end in {function.name} at {function.defined_at}"
            raise ValueError(msg)

        if not is_types_same(
            a=emulated_type_stack[0],
            b=function.return_type,
            strategy="strict-same-type",
        ):
            # type mismatch.
            raise TypecheckFunctionTypeContractOutViolatedError(
                function=function,
                type_stack=list(emulated_type_stack),
            )


def emulate_type_stack_for_operators(
    operators: Sequence[Operator],
    module: Module,
    initial_type_stack: Sequence[Type],
    current_function: Function,
    blocks_idx_shift: int = 0,
) -> Sequence[Type]:
    """Emulate and return resulting type stack from given operators.

    Functions are provided so calling it will dereference new emulation type stack.
    """
    context = TypecheckContext(
        emulated_stack_types=list(initial_type_stack),
    )

    idx_max, idx = len(operators), 0
    while idx < idx_max:
        operator, idx = operators[idx], idx + 1
        if DEBUG_TRACE_TYPESTACK:
            print(operator.location, context.emulated_stack_types)
        match operator.type:
            case (
                OperatorType.CONDITIONAL_WHILE
                | OperatorType.CONDITIONAL_FOR
                | OperatorType.CONDITIONAL_END
            ):
                ...  # Nothing here as there nothing to typecheck
            case OperatorType.CONDITIONAL_DO | OperatorType.CONDITIONAL_IF:
                context.raise_for_operator_arguments(operator, (BoolType,))

                # Acquire where this block jumps, shift due to emulation layers
                assert operator.jumps_to_operator_idx
                jumps_to_idx = operator.jumps_to_operator_idx - blocks_idx_shift

                assert operators[jumps_to_idx].type == OperatorType.CONDITIONAL_END

                type_stack = emulate_type_stack_for_operators(
                    operators=operators[idx:jumps_to_idx],
                    module=module,
                    initial_type_stack=context.emulated_stack_types[::],
                    blocks_idx_shift=blocks_idx_shift + idx,
                    current_function=current_function,
                )

                if not is_typestack_same(type_stack, context.emulated_stack_types):
                    raise TypecheckBlockStackMismatchError(
                        operator_begin=operator,
                        operator_end=operators[jumps_to_idx],
                        stack_before_block=context.emulated_stack_types,
                        stack_after_block=type_stack,
                    )

                # Skip this part as we typecheck below and acquire type stack
                idx = jumps_to_idx
            case OperatorType.PUSH_STRING:
                assert isinstance(operator.operand, str)
                string = ArrayType(
                    element_type=CharType(),
                    elements_count=len(operator.operand),
                )
                string_ptr = PointerType(points_to=string)
                context.push_types(string_ptr, I64Type())
            case OperatorType.PUSH_VARIABLE_ADDRESS:
                assert isinstance(operator.operand, str)
                variable = current_function.variables.get(operator.operand)
                if variable is None:
                    variable = module.variables.get(operator.operand)
                    if variable is None:
                        msg = f"Typechecker expect variable is known at module level or function level but it is not found in both (variable name - {operator.operand}"
                        raise ValueError(msg)
                t = variable.type
                context.push_types(PointerType(points_to=t))
            case OperatorType.PUSH_INTEGER:
                context.push_types(I64Type())
            case OperatorType.FUNCTION_RETURN:
                return context.emulated_stack_types
            case OperatorType.FUNCTION_CALL:
                assert isinstance(operator.operand, str)

                function = module.functions[operator.operand]

                if function.parameters:
                    context.raise_for_function_arguments(
                        callee=function,
                        caller=current_function,
                        at=operator,
                    )

                    # TODO(@kirillzhosul): Pointers are for now not type-checked at function call level
                    # so passing an *int to *char[] function is valid as they both are an pointer

                if function.has_return_value():
                    context.push_types(function.return_type)

            case (
                OperatorType.ARITHMETIC_MULTIPLY
                | OperatorType.ARITHMETIC_DIVIDE
                | OperatorType.ARITHMETIC_MODULUS
            ):
                # Math arithmetics operates only on integers
                # so no pointers/booleans/etc are allowed inside these intrinsics

                context.raise_for_enough_arguments(
                    operator,
                    required_args=2,
                )
                b, a = (
                    context.pop_type_from_stack(),
                    context.pop_type_from_stack(),
                )

                a_coerces = isinstance(a, I64Type)
                b_coerces = isinstance(b, I64Type)

                if not a_coerces or not b_coerces:
                    raise TypecheckInvalidBinaryMathArithmeticsError(
                        actual_lhs_type=a,
                        actual_rhs_type=b,
                        operator=operator,
                    )

                context.push_types(I64Type())
            case OperatorType.ARITHMETIC_MINUS | OperatorType.ARITHMETIC_PLUS:
                context.raise_for_enough_arguments(
                    operator,
                    required_args=2,
                )

                b, a = (
                    context.pop_type_from_stack(),
                    context.pop_type_from_stack(),
                )

                if isinstance(a, PointerType):
                    # Pointer arithmetics
                    if isinstance(b, I64Type):
                        context.push_types(PointerType(a.points_to))
                        continue
                    raise TypecheckInvalidPointerArithmeticsError(
                        actual_lhs_type=a,
                        actual_rhs_type=b,
                        operator=operator,
                    )

                # Integer math
                context.push_types(b, a)
                context.raise_for_operator_arguments(
                    operator,
                    (I64Type,),
                    (I64Type,),
                )
                context.push_types(I64Type())

            case OperatorType.MEMORY_VARIABLE_WRITE:
                context.raise_for_operator_arguments(
                    operator,
                    (PointerType,),
                    (I64Type, PointerType),
                )
            case OperatorType.MEMORY_VARIABLE_READ:
                context.raise_for_enough_arguments(
                    operator,
                    1,
                )
                ptr_t = context.pop_type_from_stack()
                if not isinstance(ptr_t, PointerType):
                    msg = f"Memory load (?>) is used to dereference an pointer but got {ptr_t} at {operator.location} (dereferencing-an-non-pointer-type)"
                    raise TypeError(msg)

                revealed_type = ptr_t.points_to
                if isinstance(revealed_type, ArrayType):
                    revealed_type = revealed_type.element_type
                context.push_types(revealed_type)
            case OperatorType.STACK_COPY:
                context.raise_for_enough_arguments(
                    operator,
                    required_args=1,
                )

                argument_type = context.pop_type_from_stack()
                context.push_types(argument_type, argument_type)
            case OperatorType.COMPARE_EQUALS | OperatorType.COMPARE_NOT_EQUALS:
                context.raise_for_operator_arguments(
                    operator,
                    (I64Type, BoolType),
                    (I64Type, BoolType),
                )
                context.push_types(BoolType())
            case (
                OperatorType.COMPARE_LESS_EQUALS
                | OperatorType.COMPARE_LESS
                | OperatorType.COMPARE_GREATER_EQUALS
                | OperatorType.COMPARE_GREATER
            ):
                context.raise_for_operator_arguments(
                    operator,
                    (I64Type,),
                    (I64Type,),
                )
                context.push_types(BoolType())
            case OperatorType.STACK_DROP:
                context.raise_for_operator_arguments(
                    operator,
                    (I64Type, PointerType),
                )
            case OperatorType.SYSCALL:
                args_count = operator.operand
                assert isinstance(args_count, int)

                argument_types = (
                    (
                        I64Type,
                        PointerType,
                    )
                    for _ in range(args_count + 1)
                )
                context.raise_for_operator_arguments(
                    operator,
                    *argument_types,
                )
                context.push_types(I64Type())
            case OperatorType.STACK_SWAP:
                context.raise_for_enough_arguments(
                    operator,
                    required_args=2,
                )
                b, a = (
                    context.pop_type_from_stack(),
                    context.pop_type_from_stack(),
                )
                context.push_types(b, a)
            case OperatorType.DEBUGGER_BREAKPOINT:
                ...
            case OperatorType.LOGICAL_OR | OperatorType.LOGICAL_AND:
                context.raise_for_operator_arguments(
                    operator,
                    (BoolType,),
                    (BoolType,),
                )
                context.push_types(BoolType())
            case (
                OperatorType.BITWISE_OR
                | OperatorType.BITWISE_AND
                | OperatorType.SHIFT_LEFT
                | OperatorType.SHIFT_RIGHT
                | OperatorType.BITWISE_XOR
            ):
                context.raise_for_operator_arguments(
                    operator,
                    (I64Type,),
                    (I64Type,),
                )
                context.push_types(I64Type())

            case OperatorType.STATIC_TYPE_CAST:
                assert isinstance(operator.operand, Type)
                to_type_cast = operator.operand
                context.raise_for_enough_arguments(
                    operator,
                    required_args=1,
                )
                context.pop_type_from_stack()
                context.push_types(to_type_cast)
            case OperatorType.STRUCT_FIELD_OFFSET:
                context.raise_for_enough_arguments(operator, required_args=1)
                struct_pointer_type = context.pop_type_from_stack()
                if not isinstance(struct_pointer_type, PointerType):
                    msg = f"Expected PUSH_STRUCT_FIELD_OFFSET to have structure pointer type on type stack but got {struct_pointer_type}"
                    raise TypeError(msg)

                struct_type = struct_pointer_type.points_to
                assert isinstance(operator.operand, str)
                _, struct_field = operator.operand.split(".", maxsplit=1)
                assert isinstance(struct_field, str), (
                    "Expected struct field as an string in operand"
                )
                if not isinstance(struct_type, StructureType):
                    msg = f"Expected PUSH_STRUCT_FIELD_OFFSET to have structure type on type stack but got {struct_type}"
                    raise TypeError(msg)

                if struct_field not in struct_type.fields:
                    msg = f"Unknown field {struct_field} for known-structure {struct_type}"
                    raise ValueError(msg)

                context.push_types(
                    PointerType(points_to=struct_type.fields[struct_field]),
                )
            case _:
                assert_never(operator.type)

    return context.emulated_stack_types


def is_typestack_same(a: Sequence[Type], b: Sequence[Type]) -> bool:
    if len(a) != len(b):
        return False
    return all(
        is_types_same(a, b, strategy="strict-same-type")
        for a, b in zip(a, b, strict=True)
    )
