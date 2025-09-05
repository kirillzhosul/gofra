from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from gofra.parser import Operator, OperatorType
from gofra.parser.intrinsics import Intrinsic

from ._context import TypecheckContext
from .exceptions import (
    TypecheckBlockStackMismatchError,
    TypecheckFunctionTypeContractOutViolatedError,
    TypecheckInvalidBinaryMathArithmeticsError,
    TypecheckInvalidPointerArithmeticsError,
)
from .types import GofraType as T
from .types import is_type_coerces_to

if TYPE_CHECKING:
    from collections.abc import MutableMapping, MutableSequence, Sequence

    from gofra.parser.functions.function import Function


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
    if len(emulated_type_stack) != len(function.type_contract_out) or not all(
        is_type_coerces_to(a, b)
        for a, b in zip(emulated_type_stack, function.type_contract_out)
    ):
        raise TypecheckFunctionTypeContractOutViolatedError(
            function=function,
            type_stack=list(emulated_type_stack),
        )


def emulate_type_stack_for_operators(
    operators: Sequence[Operator],
    global_functions: MutableMapping[str, Function],
    initial_type_stack: Sequence[T],
    current_function: Function,
    blocks_idx_shift: int = 0,
) -> MutableSequence[T]:
    """Emulate and return resulting type stack from given operators.

    Functions are provided so calling it will dereference new emulation type stack.
    """
    context = TypecheckContext(emulated_stack_types=list(initial_type_stack))

    idx_max, idx = len(operators), 0
    while idx < idx_max:
        operator, idx = operators[idx], idx + 1
        match operator.type:
            case OperatorType.WHILE | OperatorType.END:
                ...  # Nothing here as there nothing to typecheck
            case OperatorType.DO | OperatorType.IF:
                context.raise_for_arguments(operator, current_function, (T.BOOLEAN,))

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

                if type_stack != context.emulated_stack_types:
                    raise TypecheckBlockStackMismatchError(
                        operator_begin=operator,
                        operator_end=operators[jumps_to_idx],
                        stack_before_block=context.emulated_stack_types,
                        stack_after_block=type_stack,
                    )

                # Skip this part as we typecheck below and acquire type stack
                idx = jumps_to_idx
            case OperatorType.PUSH_STRING:
                context.push_types(T.POINTER, T.INTEGER)
            case OperatorType.PUSH_MEMORY_POINTER:
                context.push_types(T.POINTER)
            case OperatorType.PUSH_INTEGER:
                assert not operator.has_optimizations, "TBD"
                assert not operator.infer_type_after_optimization, "TBD"
                context.push_types(T.INTEGER)
            case OperatorType.FUNCTION_RETURN:
                return context.emulated_stack_types
            case OperatorType.FUNCTION_CALL:
                assert isinstance(operator.operand, str)

                function = global_functions[operator.operand]
                type_contract_in = function.type_contract_in

                if type_contract_in:
                    context.raise_for_arguments(
                        function,
                        current_function,
                        *((t,) for t in type_contract_in),
                        operator=operator,
                    )
                context.push_types(*function.type_contract_out)
            case OperatorType.INTRINSIC:
                assert isinstance(operator.operand, Intrinsic)
                match operator.operand:
                    case Intrinsic.INCREMENT | Intrinsic.DECREMENT:
                        context.raise_for_arguments(
                            operator,
                            current_function,
                            (T.INTEGER,),
                        )
                        context.push_types(T.INTEGER)
                    case Intrinsic.MULTIPLY | Intrinsic.DIVIDE | Intrinsic.MODULUS:
                        # Math arithmetics operates only on integers
                        # so no pointers/booleans/etc are allowed inside these intrinsics

                        context.raise_for_enough_arguments(
                            operator,
                            current_function,
                            required_args=2,
                        )
                        b, a = (
                            context.pop_type_from_stack(),
                            context.pop_type_from_stack(),
                        )

                        a_coerces = is_type_coerces_to(a, T.INTEGER)
                        b_coerces = is_type_coerces_to(b, T.INTEGER)

                        if not a_coerces or not b_coerces:
                            raise TypecheckInvalidBinaryMathArithmeticsError(
                                actual_lhs_type=a,
                                actual_rhs_type=b,
                                operator=operator,
                            )

                        context.push_types(T.INTEGER)
                    case Intrinsic.MINUS | Intrinsic.PLUS:
                        context.raise_for_enough_arguments(
                            operator,
                            current_function,
                            required_args=2,
                        )

                        b, a = (
                            context.pop_type_from_stack(),
                            context.pop_type_from_stack(),
                        )

                        if a == T.POINTER:
                            # Pointer arithmetics
                            if is_type_coerces_to(b, T.INTEGER):
                                context.push_types(T.POINTER)
                                continue
                            raise TypecheckInvalidPointerArithmeticsError(
                                actual_lhs_type=a,
                                actual_rhs_type=b,
                                operator=operator,
                            )

                        # Integer math
                        context.push_types(b, a)
                        context.raise_for_arguments(
                            operator,
                            current_function,
                            (T.INTEGER,),
                            (T.INTEGER,),
                        )
                        context.push_types(T.INTEGER)

                    case Intrinsic.MEMORY_STORE:
                        context.raise_for_arguments(
                            operator,
                            current_function,
                            (T.POINTER,),
                            (T.INTEGER, T.BOOLEAN, T.POINTER),
                        )
                    case Intrinsic.MEMORY_LOAD:
                        context.raise_for_arguments(
                            operator,
                            current_function,
                            (T.POINTER,),
                        )
                        context.push_types(T.ANY)
                    case Intrinsic.COPY:
                        context.raise_for_enough_arguments(
                            operator,
                            current_function,
                            required_args=1,
                        )

                        argument_type = context.pop_type_from_stack()
                        context.push_types(argument_type, argument_type)
                    case (
                        Intrinsic.EQUAL
                        | Intrinsic.LESS_EQUAL_THAN
                        | Intrinsic.LESS_THAN
                        | Intrinsic.GREATER_EQUAL_THAN
                        | Intrinsic.GREATER_THAN
                        | Intrinsic.NOT_EQUAL
                    ):
                        context.raise_for_arguments(
                            operator,
                            current_function,
                            (T.ANY,),
                            (T.ANY,),
                        )
                        context.push_types(T.BOOLEAN)
                    case Intrinsic.DROP:
                        context.raise_for_arguments(
                            operator,
                            current_function,
                            (T.ANY,),
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

                        argument_types = ((T.ANY,) for _ in range(args_count))
                        context.raise_for_arguments(
                            operator,
                            current_function,
                            *argument_types,
                        )
                        context.push_types(T.INTEGER)
                    case Intrinsic.SWAP:
                        context.raise_for_enough_arguments(
                            operator,
                            current_function,
                            required_args=2,
                        )
                        b, a = (
                            context.pop_type_from_stack(),
                            context.pop_type_from_stack(),
                        )
                        context.push_types(b, a)
                    case _:
                        assert_never(operator.operand)
            case _:
                assert_never(operator.type)

    return context.emulated_stack_types
