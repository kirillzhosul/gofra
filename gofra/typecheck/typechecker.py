from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from gofra.parser import Operator, OperatorType
from gofra.parser.intrinsics import Intrinsic
from gofra.typecheck.errors.return_value_missing import ReturnValueMissingTypecheckError
from gofra.types import Type
from gofra.types.comparsion import is_types_same
from gofra.types.composite.array import ArrayType
from gofra.types.composite.pointer import PointerType
from gofra.types.primitive.boolean import BoolType
from gofra.types.primitive.character import CharType
from gofra.types.primitive.integers import I64Type
from gofra.types.primitive.void import VoidType

from ._context import TypecheckContext
from .exceptions import (
    TypecheckBlockStackMismatchError,
    TypecheckFunctionTypeContractOutViolatedError,
    TypecheckInvalidBinaryMathArithmeticsError,
    TypecheckInvalidPointerArithmeticsError,
)

if TYPE_CHECKING:
    from collections.abc import MutableMapping, MutableSequence, Sequence

    from gofra.parser.functions.function import Function


# TODO(@kirillzhosul): Probably be something like an debug flag
# Traces each operation on stack to search bugs in typechecker
DEBUG_TRACE_TYPESTACK = False


def validate_type_safety(functions: MutableMapping[str, Function]) -> None:
    """Validate type safety of an program by type checking all given functions."""
    for function in functions.values():
        if function.external_definition_link_to:
            continue
        validate_function_type_safety(
            function=function,
            global_functions=functions,
        )


def validate_function_type_safety(
    function: Function,
    global_functions: MutableMapping[str, Function],
) -> None:
    """Emulate and validate function type safety inside."""
    emulated_type_stack = emulate_type_stack_for_operators(
        operators=function.source,
        global_functions=global_functions,
        initial_type_stack=list(function.type_contract_in),
        current_function=function,
    )

    # TODO(@kirillzhosul): Probably this should be refactored due to overall new complexity of an `ANY` and coercion.
    has_retval = not is_types_same(function.type_contract_out, VoidType())
    if not has_retval and emulated_type_stack:
        # function must not return any
        raise TypecheckFunctionTypeContractOutViolatedError(
            function=function,
            type_stack=list(emulated_type_stack),
        )
    if has_retval:
        if len(emulated_type_stack) == 0:
            raise ReturnValueMissingTypecheckError(owner=function)

        if len(emulated_type_stack) > 1:
            raise ValueError("ambigious stack size at function end")

        if not is_types_same(
            a=emulated_type_stack[0],
            b=function.type_contract_out,
            strategy="strict-same-type",
        ):
            # type mismatch.
            raise TypecheckFunctionTypeContractOutViolatedError(
                function=function,
                type_stack=list(emulated_type_stack),
            )


def emulate_type_stack_for_operators(
    operators: Sequence[Operator],
    global_functions: MutableMapping[str, Function],
    initial_type_stack: Sequence[Type],
    current_function: Function,
    blocks_idx_shift: int = 0,
) -> MutableSequence[Type]:
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
            print(operator.token.location, context.emulated_stack_types)
        match operator.type:
            case OperatorType.WHILE | OperatorType.END:
                ...  # Nothing here as there nothing to typecheck
            case OperatorType.DO | OperatorType.IF:
                context.raise_for_operator_arguments(operator, (BoolType,))

                # Acquire where this block jumps, shift due to emulation layers
                assert operator.jumps_to_operator_idx
                jumps_to_idx = operator.jumps_to_operator_idx - blocks_idx_shift

                assert operators[jumps_to_idx].type == OperatorType.END

                type_stack = emulate_type_stack_for_operators(
                    operators=operators[idx:jumps_to_idx],
                    global_functions=global_functions,
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
            case OperatorType.PUSH_MEMORY_POINTER:
                assert isinstance(operator.operand, tuple)
                t = operator.operand[1]
                context.push_types(PointerType(points_to=t))
            case OperatorType.PUSH_INTEGER:
                assert not operator.has_optimizations, "TBD"
                assert not operator.infer_type_after_optimization, "TBD"
                context.push_types(I64Type())
            case OperatorType.FUNCTION_RETURN:
                return context.emulated_stack_types
            case OperatorType.FUNCTION_CALL:
                assert isinstance(operator.operand, str)

                function = global_functions[operator.operand]
                type_contract_in = function.type_contract_in

                if type_contract_in:
                    context.raise_for_function_arguments(
                        callee=function,
                        caller=current_function,
                        at=operator,
                    )

                    # TODO(@kirillzhosul): Pointers are for now not type-checked at function call level
                    # so passing an *int to *char[] funciton is valid as they both are an pointer

                if not isinstance(function.type_contract_out, VoidType):
                    context.push_types(function.type_contract_out)

            case OperatorType.INTRINSIC:
                assert isinstance(operator.operand, Intrinsic)
                match operator.operand:
                    case Intrinsic.INCREMENT | Intrinsic.DECREMENT:
                        context.raise_for_operator_arguments(
                            operator,
                            (I64Type,),
                        )
                        context.push_types(I64Type())
                    case Intrinsic.MULTIPLY | Intrinsic.DIVIDE | Intrinsic.MODULUS:
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
                    case Intrinsic.MINUS | Intrinsic.PLUS:
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

                    case Intrinsic.MEMORY_STORE:
                        context.raise_for_operator_arguments(
                            operator,
                            (PointerType,),
                            (I64Type, PointerType),
                        )
                    case Intrinsic.MEMORY_LOAD:
                        context.raise_for_enough_arguments(
                            operator,
                            1,
                        )
                        ptr_t = context.pop_type_from_stack()
                        if not isinstance(ptr_t, PointerType):
                            msg = f"Memory load (?>) is used to dereference an pointer but got {ptr_t} at {operator.token.location} (dereferencing-an-non-pointer-type)"
                            raise TypeError(msg)

                        revealed_type = ptr_t.points_to
                        if isinstance(revealed_type, ArrayType):
                            revealed_type = revealed_type.element_type
                        context.push_types(revealed_type)
                    case Intrinsic.COPY:
                        context.raise_for_enough_arguments(
                            operator,
                            required_args=1,
                        )

                        argument_type = context.pop_type_from_stack()
                        context.push_types(argument_type, argument_type)
                    case Intrinsic.EQUAL | Intrinsic.NOT_EQUAL:
                        context.raise_for_operator_arguments(
                            operator,
                            (I64Type, BoolType),
                            (I64Type, BoolType),
                        )
                        context.push_types(BoolType())
                    case (
                        Intrinsic.LESS_EQUAL_THAN
                        | Intrinsic.LESS_THAN
                        | Intrinsic.GREATER_EQUAL_THAN
                        | Intrinsic.GREATER_THAN
                    ):
                        context.raise_for_operator_arguments(
                            operator,
                            (I64Type,),
                            (I64Type,),
                        )
                        context.push_types(BoolType())
                    case Intrinsic.DROP:
                        context.raise_for_operator_arguments(
                            operator,
                            (I64Type, PointerType),
                        )
                    case (
                        Intrinsic.SYSCALL0
                        | Intrinsic.SYSCALL1
                        | Intrinsic.SYSCALL2
                        | Intrinsic.SYSCALL3
                        | Intrinsic.SYSCALL4
                        | Intrinsic.SYSCALL5
                        | Intrinsic.SYSCALL6
                    ):
                        assert not operator.syscall_optimization_injected_args
                        assert not operator.syscall_optimization_omit_result
                        args_count = operator.get_syscall_arguments_count()

                        argument_types = (
                            (
                                I64Type,
                                PointerType,
                            )
                            for _ in range(args_count)
                        )
                        context.raise_for_operator_arguments(
                            operator,
                            *argument_types,
                        )
                        context.push_types(I64Type())
                    case Intrinsic.SWAP:
                        context.raise_for_enough_arguments(
                            operator,
                            required_args=2,
                        )
                        b, a = (
                            context.pop_type_from_stack(),
                            context.pop_type_from_stack(),
                        )
                        context.push_types(b, a)
                    case Intrinsic.BREAKPOINT:
                        ...
                    case Intrinsic.LOGICAL_OR | Intrinsic.LOGICAL_AND:
                        context.raise_for_operator_arguments(
                            operator,
                            (BoolType,),
                            (BoolType,),
                        )
                        context.push_types(BoolType())
                    case (
                        Intrinsic.BITWISE_OR
                        | Intrinsic.BITWISE_AND
                        | Intrinsic.BITSHIFT_LEFT
                        | Intrinsic.BITSHIFT_RIGHT
                    ):
                        context.raise_for_operator_arguments(
                            operator,
                            (I64Type,),
                            (I64Type,),
                        )
                        context.push_types(I64Type())
                    case _:
                        assert_never(operator.operand)
            case OperatorType.TYPECAST:
                assert isinstance(operator.operand, Type)
                to_type_cast = operator.operand
                context.raise_for_enough_arguments(
                    operator,
                    required_args=1,
                )
                context.pop_type_from_stack()
                context.push_types(to_type_cast)
            case OperatorType.VARIABLE_DEFINE:
                raise ValueError
            case _:
                assert_never(operator.type)

    return context.emulated_stack_types


def is_typestack_same(a: Sequence[Type], b: Sequence[Type]) -> bool:
    return list(map(type, a)) == list(map(type, b))
