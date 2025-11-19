from __future__ import annotations

from typing import TYPE_CHECKING, Literal, NamedTuple, assert_never

from gofra.cli.output import cli_message
from gofra.consts import GOFRA_ENTRY_POINT
from gofra.hir.operator import OperatorType
from gofra.hir.variable import Variable, VariableStorageClass
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
from gofra.typecheck.static_linter import (
    lint_stack_memory_retval,
    lint_typecast_same_type,
    lint_unused_function_local_variables,
)
from gofra.types import Type
from gofra.types.comparison import is_types_same, is_typestack_same
from gofra.types.composite.array import ArrayType
from gofra.types.composite.pointer import PointerMemoryLocation, PointerType
from gofra.types.composite.string import StringType
from gofra.types.composite.structure import StructureType
from gofra.types.primitive.boolean import BoolType
from gofra.types.primitive.character import CharType
from gofra.types.primitive.floats import F64Type
from gofra.types.primitive.integers import I64Type

from ._context import TypecheckContext
from .exceptions import (
    TypecheckBlockStackMismatchError,
    TypecheckFunctionTypeContractOutViolatedError,
    TypecheckInvalidBinaryMathArithmeticsError,
    TypecheckInvalidPointerArithmeticsError,
)

if TYPE_CHECKING:
    from collections.abc import MutableMapping, Sequence

    from gofra.hir.function import Function
    from gofra.hir.module import Module
    from gofra.hir.operator import Operator

# TODO!!!(@kirillzhosul): Typechecker may skip typechecking if early-return is occurred  # noqa: TD002, TD004

# TODO(@kirillzhosul): Probably be something like an debug flag
# Traces each operation on stack to search bugs in typechecker
DEBUG_TRACE_TYPESTACK = False


class EmulatedTypeBlock(NamedTuple):
    types: Sequence[Type]
    reason: Literal[
        "end-of-block",  # Reached its end when has no more operators
        "early-return",  # Hit `return` (not for end-of-block)
        "no-return-func-call",  # Called to a function which is defined as no return - imply that cannot really execute anything after that
    ]
    references_variables: MutableMapping[str, Variable[Type]]


def validate_type_safety(
    module: Module,
    *,
    strict_expect_entry_point: bool = True,
) -> None:
    """Validate type safety of an program by type checking all given functions."""
    functions = list(module.functions.values())
    if strict_expect_entry_point and GOFRA_ENTRY_POINT not in module.functions:
        raise ParserNoEntryFunctionError

    if GOFRA_ENTRY_POINT in module.functions:
        entry_point = module.functions[GOFRA_ENTRY_POINT]

        _validate_entry_point_signature(entry_point)

    global_var_references: MutableMapping[str, Variable[Type]] = {}
    for function in functions:
        if function.is_external:
            # Skip symbols that are has no compile-time known executable operators as have nothing to typecheck
            continue

        func_block = validate_function_type_safety(
            function=function,
            module=module,
        )
        global_var_references |= {
            v.name: v
            for v in func_block.references_variables.values()
            if v.is_global_scope
        }

    unused_global_variables = [
        module.variables[vn]
        for vn in set(module.variables) - set(global_var_references)
    ]
    for variable in unused_global_variables:
        if variable.is_constant:
            # TODO(@kirillzhosul): Compiler (parser) actually inlines them and TC does not knows about their usages
            continue
        cli_message(
            "WARNING",
            f"Unused non-constant global variable '{variable.name}' defined at {variable.defined_at}",
        )


def validate_function_type_safety(
    function: Function,
    module: Module,
) -> EmulatedTypeBlock:
    """Emulate and validate function type safety inside."""
    func_block = emulate_type_stack_for_operators(
        operators=function.operators,
        module=module,
        initial_type_stack=list(function.parameters),
        current_function=function,
    )
    emulated_type_stack, reason, references_variables = func_block

    # TODO(@kirillzhosul): Probably this should be refactored due to overall new complexity of an `ANY` and coercion.

    if reason == "no-return-func-call" and not function.is_no_return:
        cli_message(
            "WARNING",
            f"Function '{function.name}' defined at {function.defined_at} calls to no-return function inside no conditional blocks, consider propagate no-return attribute",
        )

    if function.is_no_return and function.has_return_value():
        msg = f"Cannot return value from function '{function.name}' defined at {function.defined_at}, it has no_return attribute"
        raise ValueError(msg)

    lint_unused_function_local_variables(function, references_variables)
    if not function.has_return_value() and emulated_type_stack:
        # function must not return any
        raise TypecheckFunctionTypeContractOutViolatedError(
            function=function,
            type_stack=list(emulated_type_stack),
        )

    if function.has_return_value():  # and reason != "no-return-func-call":
        _validate_retval_stack(function, emulated_type_stack)
        retval_t = emulated_type_stack[0]
        lint_stack_memory_retval(function, retval_t)

    return func_block


def emulate_type_stack_for_operators(
    operators: Sequence[Operator],
    module: Module,
    initial_type_stack: Sequence[Type],
    current_function: Function,
    blocks_idx_shift: int = 0,
) -> EmulatedTypeBlock:
    """Emulate and return resulting type stack from given operators.

    Functions are provided so calling it will dereference new emulation type stack.
    """
    context = TypecheckContext(
        emulated_stack_types=list(initial_type_stack),
    )

    references_variables: MutableMapping[
        str,
        Variable[Type],
    ] = {}  # merge into context?
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

                type_stack, reason, block_references_variables = (
                    emulate_type_stack_for_operators(
                        operators=operators[idx:jumps_to_idx],
                        module=module,
                        initial_type_stack=context.emulated_stack_types[::],
                        blocks_idx_shift=blocks_idx_shift + idx,
                        current_function=current_function,
                    )
                )

                references_variables |= block_references_variables
                if reason != "early-return" and not is_typestack_same(
                    type_stack,
                    context.emulated_stack_types,
                ):
                    raise TypecheckBlockStackMismatchError(
                        operator_begin=operator,
                        operator_end=operators[jumps_to_idx],
                        stack_before_block=context.emulated_stack_types,
                        stack_after_block=type_stack,
                    )

                # TODO(@kirillzhosul): validate return stack if got early-return

                # Skip this part as we typecheck below and acquire type stack
                idx = jumps_to_idx
            case OperatorType.PUSH_STRING:
                assert isinstance(operator.operand, str)
                context.push_types(
                    PointerType(
                        points_to=StringType(),
                        memory_location=PointerMemoryLocation.STATIC,
                    ),
                )
            case OperatorType.PUSH_VARIABLE_ADDRESS:
                assert isinstance(operator.operand, str)
                varname = operator.operand
                variable = {**module.variables, **current_function.variables}[varname]

                # Track usages of each variable
                references_variables[varname] = variable

                memory_location = {
                    VariableStorageClass.STACK: PointerMemoryLocation.STACK,
                    VariableStorageClass.STATIC: PointerMemoryLocation.STATIC,
                }[variable.storage_class]

                t = variable.type
                ptr = PointerType(
                    points_to=t,
                    memory_location=memory_location,
                )
                context.push_types(ptr)
            case OperatorType.PUSH_INTEGER:
                context.push_types(I64Type())
            case OperatorType.PUSH_FLOAT:
                context.push_types(F64Type())
            case OperatorType.FUNCTION_RETURN:
                type_block = EmulatedTypeBlock(
                    context.emulated_stack_types,
                    reason="early-return",
                    references_variables=references_variables,
                )
                if operators[idx:]:
                    cli_message(
                        "WARNING",
                        f"Function '{current_function.name}' has operators after early-return at {operator.location}! This is unreachable code starting at {operators[idx].location}!",
                    )
                return type_block
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

                if function.is_no_return:
                    if operators[idx:]:
                        cli_message(
                            "WARNING",
                            f"Function '{current_function.name}' has operators after calling no-return function '{function.name}' at {operator.location}! This is unreachable code starting at {operators[idx].location}!",
                        )
                    return EmulatedTypeBlock(
                        context.emulated_stack_types,
                        reason="no-return-func-call",
                        references_variables=references_variables,
                    )
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
                    (I64Type, PointerType, BoolType, CharType),
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
                context.raise_for_enough_arguments(operator, required_args=1)
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
                # TODO(@kirillzhosul): Generic comparison
                context.raise_for_operator_arguments(
                    operator,
                    (I64Type,),
                    (I64Type,),
                )
                context.push_types(BoolType())
            case OperatorType.STACK_DROP:
                context.raise_for_enough_arguments(operator, 1)
                context.consume_n_arguments(1)
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
                context.raise_for_enough_arguments(operator, required_args=2)
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
                context.raise_for_enough_arguments(operator, required_args=1)
                previous_type = context.pop_type_from_stack()
                lint_typecast_same_type(
                    t_from=previous_type,
                    t_to=to_type_cast,
                    at=operator.token.location,
                )
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

    return EmulatedTypeBlock(
        context.emulated_stack_types,
        reason="end-of-block",
        references_variables=references_variables,
    )


def _validate_entry_point_signature(entry_point: Function) -> None:
    # TODO(@kirillzhosul): these parser errors comes from legacy entry point validation, must be reworked later - https://github.com/kirillzhosul/gofra/issues/28
    if entry_point.is_external or entry_point.is_inline:
        raise ParserEntryPointFunctionModifiersError

    retval_t = entry_point.return_type
    if entry_point.has_return_value() and not isinstance(retval_t, I64Type):
        raise EntryPointReturnTypeMismatchTypecheckError(return_type=retval_t)

    if entry_point.parameters:
        raise EntryPointParametersMismatchTypecheckError(
            parameters=entry_point.parameters,
        )


def _validate_retval_stack(
    function: Function,
    emulated_type_stack: Sequence[Type],
) -> None:
    if len(emulated_type_stack) == 0:
        raise ReturnValueMissingTypecheckError(owner=function)

    retval_t = emulated_type_stack[0]
    if len(emulated_type_stack) > 1:
        msg = f"Ambiguous stack size at function end in {function.name} at {function.defined_at}"
        raise ValueError(msg)

    if not is_types_same(
        a=retval_t,
        b=function.return_type,
        strategy="strict-same-type",
    ):
        # type mismatch.
        raise TypecheckFunctionTypeContractOutViolatedError(
            function=function,
            type_stack=list(emulated_type_stack),
        )
