from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, assert_never

from libgofra.hir.operator import FunctionCallOperand, OperatorType
from libgofra.hir.variable import Variable, VariableStorageClass
from libgofra.typecheck.entry_point import validate_entry_point_signature
from libgofra.typecheck.errors.no_main_entry_function import NoMainEntryFunctionError
from libgofra.typecheck.errors.return_value_missing import (
    ReturnValueMissingTypecheckError,
)
from libgofra.typecheck.errors.user_defined_compile_time_error import (
    UserDefinedCompileTimeError,
)
from libgofra.typecheck.static_linter import (
    emit_no_return_attribute_propagation_warning,
    emit_unreachable_code_after_early_return_warning,
    emit_unreachable_code_after_no_return_call_warning,
    emit_unused_global_variable_warning,
    lint_stack_memory_retval,
    lint_structure_types,
    lint_typecast_same_type,
    lint_unused_function_local_variables,
    lint_variables_initializer,
)
from libgofra.types import Type
from libgofra.types.comparison import is_types_same, is_typestack_same
from libgofra.types.composite.array import ArrayType
from libgofra.types.composite.function import FunctionType
from libgofra.types.composite.pointer import PointerMemoryLocation, PointerType
from libgofra.types.composite.string import StringType
from libgofra.types.composite.structure import StructureType
from libgofra.types.primitive.boolean import BoolType
from libgofra.types.primitive.character import CharType
from libgofra.types.primitive.floats import F64Type
from libgofra.types.primitive.integers import I64Type, IntegerType
from libgofra.types.primitive.void import VoidType

from ._scope import TypecheckScope
from .exceptions import (
    TypecheckBlockStackMismatchError,
    TypecheckFunctionTypeContractOutViolatedError,
    TypecheckInvalidBinaryMathArithmeticsError,
    TypecheckInvalidPointerArithmeticsError,
)

if TYPE_CHECKING:
    from collections.abc import Callable, MutableMapping, Sequence

    from libgofra.hir.function import Function
    from libgofra.hir.module import Module
    from libgofra.hir.operator import Operator
    from libgofra.lexer.tokens import TokenLocation

# TODO!!!(@kirillzhosul): Typechecker may skip typechecking if early-return is occurred  # noqa: TD004

# TODO(@kirillzhosul): Probably be something like an debug flag
# Traces each operation on stack to search bugs in typechecker
DEBUG_TRACE_TYPESTACK = False


@dataclass
class EmulatedTypeBlock:
    types: Sequence[Type]
    reason: Literal[
        "end-of-block",  # Reached its end when has no more operators
        "early-return",  # Hit `return` (not for end-of-block)
        "no-return-func-call",  # Called to a function which is defined as no return - imply that cannot really execute anything after that
    ]
    references_variables: MutableMapping[str, Variable[Type]]

    @property
    def global_references_variables(self) -> MutableMapping[str, Variable[Type]]:
        return {
            v.name: v for v in self.references_variables.values() if v.is_global_scope
        }


def on_lint_warning_suppressed(_: str) -> None:
    return None


def validate_type_safety(
    module: Module,
    *,
    strict_expect_entry_point: bool = True,
    on_lint_warning: Callable[[str], None] | None,
    entry_point_name: str = "main",
) -> None:
    """Validate type safety of an program by type checking all given functions."""
    if on_lint_warning is None:
        on_lint_warning = on_lint_warning_suppressed

    if strict_expect_entry_point:
        entry_point = module.functions.get(entry_point_name)

        if not entry_point:
            raise NoMainEntryFunctionError(expected_entry_name=entry_point_name)
        validate_entry_point_signature(entry_point)

    lint_structure_types(on_lint_warning, module.structures)
    lint_variables_initializer(on_lint_warning, module.variables)
    global_var_references: MutableMapping[str, Variable[Type]] = {}
    functions = list(module.functions.values())
    for function in functions:
        if function.is_external:
            # Skip symbols that are has no compile-time known executable operators as have nothing to typecheck
            continue

        func_block = validate_function_type_safety(
            function=function,
            module=module,
            on_lint_warning=on_lint_warning,
        )
        global_var_references |= func_block.global_references_variables

    unused_global_variables = [
        module.variables[vn]
        for vn in set(module.variables) - set(global_var_references)
    ]
    for variable in unused_global_variables:
        if variable.is_constant:
            # TODO(@kirillzhosul): Compiler (parser) actually inlines them and TC does not knows about their usages
            continue
        emit_unused_global_variable_warning(on_lint_warning, variable)


def validate_function_type_safety(
    function: Function,
    module: Module,
    *,
    on_lint_warning: Callable[[str], None],
) -> EmulatedTypeBlock:
    """Emulate and validate function type safety inside."""
    func_block = emulate_type_stack_for_operators(
        operators=function.operators,
        module=module,
        initial_type_stack=list(function.parameters),
        on_lint_warning=on_lint_warning,
        current_function=function,
    )

    # TODO(@kirillzhosul): Probably this should be refactored due to overall new complexity of an `ANY` and coercion.

    if func_block.reason == "no-return-func-call" and not function.is_no_return:
        emit_no_return_attribute_propagation_warning(on_lint_warning, function)

    if function.is_no_return and function.has_return_value():
        msg = f"Cannot return value from function '{function.name}' defined at {function.defined_at}, it has no_return attribute"
        raise ValueError(msg)

    lint_unused_function_local_variables(
        on_lint_warning,
        function,
        func_block.references_variables,
    )
    if not function.has_return_value() and func_block.types:
        # function must not return any
        raise TypecheckFunctionTypeContractOutViolatedError(
            function=function,
            type_stack=list(func_block.types),
        )

    _validate_retval_stack(function, func_block.types, return_hit_at=None)
    if function.has_return_value():  # and reason != "no-return-func-call":
        retval_t = func_block.types[0]
        lint_stack_memory_retval(on_lint_warning, function, retval_t)

    return func_block


def emulate_type_stack_for_operators(  # noqa: PLR0913
    operators: Sequence[Operator],
    module: Module,
    initial_type_stack: Sequence[Type],
    current_function: Function,
    on_lint_warning: Callable[[str], None],
    blocks_idx_shift: int = 0,
    references_variables: MutableMapping[str, Variable[Type]] | None = None,
) -> EmulatedTypeBlock:
    """Emulate and return resulting type stack from given operators.

    Functions are provided so calling it will dereference new emulation type stack.
    """
    scope = TypecheckScope(types=list(initial_type_stack))

    if references_variables is None:
        references_variables = {}  # merge into scope?
    idx_max, idx = len(operators), 0
    while idx < idx_max:
        operator, idx = operators[idx], idx + 1
        if DEBUG_TRACE_TYPESTACK:
            print(operator.location, scope.types)
        match operator.type:
            case (
                OperatorType.CONDITIONAL_WHILE
                | OperatorType.CONDITIONAL_FOR
                | OperatorType.CONDITIONAL_END
            ):
                # These operators does not perform any *real* operations
                # they just mark conditional block start
                pass
            case OperatorType.CONDITIONAL_DO | OperatorType.CONDITIONAL_IF:
                # Treat integer also as *comparable*
                scope.raise_for_operator_arguments(operator, (BoolType, IntegerType))

                # Acquire where this block jumps, shift due to emulation layers
                assert operator.jumps_to_operator_idx
                jumps_to_idx = operator.jumps_to_operator_idx - blocks_idx_shift
                assert operators[jumps_to_idx].type == OperatorType.CONDITIONAL_END

                block = emulate_type_stack_for_operators(
                    operators=operators[idx:jumps_to_idx],
                    module=module,
                    initial_type_stack=scope.types[::],
                    blocks_idx_shift=blocks_idx_shift + idx,
                    current_function=current_function,
                    on_lint_warning=on_lint_warning,
                    references_variables=references_variables,
                )

                if block.reason not in (
                    "early-return",
                    "no-return-func-call",
                ) and not is_typestack_same(
                    block.types,
                    scope.types,
                ):
                    # If block reached its end it must not modify stack
                    raise TypecheckBlockStackMismatchError(
                        operator_begin=operator,
                        operator_end=operators[jumps_to_idx],
                        stack_before_block=scope.types,
                        stack_after_block=block.types,
                    )

                # Skip this part as we typecheck below and acquire type stack
                idx = jumps_to_idx
            case _:
                etb = _emulate_scope_unconditional_hir_operator(
                    operators,
                    current_function,
                    module,
                    operator,
                    scope,
                    references_variables,
                    idx,
                    on_lint_warning,
                    is_sub_scope=blocks_idx_shift == 0,
                )
                if etb:
                    return etb

    return EmulatedTypeBlock(
        scope.types,
        reason="end-of-block",
        references_variables=references_variables,
    )


def _emulate_scope_unconditional_hir_operator(  # noqa: PLR0913
    operators: Sequence[Operator],
    current_function: Function,
    module: Module,
    operator: Operator,
    scope: TypecheckScope,
    references_variables: MutableMapping[str, Variable[Type]],
    idx: int,
    on_lint_warning: Callable[[str], None],
    *,
    is_sub_scope: bool,
) -> EmulatedTypeBlock | None:
    match operator.type:
        case OperatorType.INLINE_RAW_ASM:
            # Assembly cannot be typechecked
            # unless we introduce more powerful constructions of inlining assembly
            # (potentially this allows typechecking)
            ...
        case OperatorType.COMPILE_TIME_ERROR:
            # Raise an error if this code is reachable at type checking stage
            # possibly, this can be not a part of typechecker
            # but currently only typechecker validates any sort of DCE
            assert isinstance(operator.operand, str)
            raise UserDefinedCompileTimeError(
                message=operator.operand,
                at=operator.token.location,
            )
        case (
            OperatorType.CONDITIONAL_WHILE
            | OperatorType.CONDITIONAL_FOR
            | OperatorType.CONDITIONAL_END
        ):
            ...  # Nothing here as there nothing to typecheck
        case OperatorType.DEBUGGER_BREAKPOINT:
            ...
        case OperatorType.CONDITIONAL_DO | OperatorType.CONDITIONAL_IF:
            raise AssertionError
        case OperatorType.PUSH_STRING:
            assert isinstance(operator.operand, str)
            scope.push_types(
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
            scope.push_types(ptr)
        case OperatorType.PUSH_INTEGER:
            scope.push_types(I64Type())
        case OperatorType.PUSH_FLOAT:
            scope.push_types(F64Type())
        case OperatorType.FUNCTION_RETURN:
            type_block = EmulatedTypeBlock(
                scope.types,
                reason="early-return",
                references_variables=references_variables,
            )
            if operators[idx:]:
                emit_unreachable_code_after_early_return_warning(
                    on_lint_warning,
                    current_function,
                    return_at=operator.location,
                    unreachable_at=operators[idx].location,
                )

            _validate_retval_stack(
                current_function,
                scope.types,
                return_hit_at=operator.location,
            )
            return type_block
        case OperatorType.FUNCTION_CALL:
            assert isinstance(operator.operand, FunctionCallOperand)

            operand = operator.operand
            function = module.resolve_function_dependency(
                operand.module,
                operand.get_name(),
            )

            assert function is not None, (
                "Function existence must be resolved before typechecker stage!"
            )
            if function.parameters:
                scope.raise_for_function_arguments(
                    callee=function,
                    caller=current_function,
                    at=operator,
                )

                # TODO(@kirillzhosul): Pointers are for now not type-checked at function call level
                # so passing an *int to *char[] function is valid as they both are an pointer

            if function == current_function and is_sub_scope:
                on_lint_warning(
                    f"Function '{current_function.name}' cannot return without recursion. This will lead to infinite recursion loop. Recursive call at {operator.location}",
                )

            if function.is_no_return:
                if operators[idx:]:
                    emit_unreachable_code_after_no_return_call_warning(
                        on_lint_warning,
                        call_from=current_function,
                        call_at=operator.location,
                        unreachable_at=operators[idx].location,
                        callee=function,
                    )
                return EmulatedTypeBlock(
                    scope.types,
                    reason="no-return-func-call",
                    references_variables=references_variables,
                )
            if function.has_return_value():
                scope.push_types(function.return_type)

        case (
            OperatorType.ARITHMETIC_MULTIPLY
            | OperatorType.ARITHMETIC_DIVIDE
            | OperatorType.ARITHMETIC_MODULUS
        ):
            # Math arithmetics operates only on integers
            # so no pointers/booleans/etc are allowed inside these intrinsics

            scope.raise_for_enough_arguments(
                operator,
                required_args=2,
            )
            b, a = (
                scope.pop_type_from_stack(),
                scope.pop_type_from_stack(),
            )

            a_coerces = isinstance(a, IntegerType)
            b_coerces = isinstance(b, IntegerType)

            if not a_coerces or not b_coerces:
                raise TypecheckInvalidBinaryMathArithmeticsError(
                    actual_lhs_type=a,
                    actual_rhs_type=b,
                    operator=operator,
                )

            scope.push_types(I64Type())
        case OperatorType.ARITHMETIC_MINUS | OperatorType.ARITHMETIC_PLUS:
            scope.raise_for_enough_arguments(
                operator,
                required_args=2,
            )

            b, a = (
                scope.pop_type_from_stack(),
                scope.pop_type_from_stack(),
            )

            if isinstance(a, PointerType):
                # Pointer arithmetics
                if isinstance(b, IntegerType):
                    scope.push_types(PointerType(a.points_to))
                    return None
                raise TypecheckInvalidPointerArithmeticsError(
                    actual_lhs_type=a,
                    actual_rhs_type=b,
                    operator=operator,
                )

            # Integer math
            scope.push_types(b, a)
            scope.raise_for_operator_arguments(
                operator,
                (I64Type,),
                (I64Type,),
            )
            scope.push_types(I64Type())

        case OperatorType.MEMORY_VARIABLE_WRITE:
            mut_scope = scope.types[:2:]
            scope.raise_for_operator_arguments(
                operator,
                (PointerType,),
                (I64Type, PointerType, BoolType, CharType, FunctionType),
            )
            value_holder_type = mut_scope[-2]
            assert isinstance(value_holder_type, PointerType), (
                operator.location,
                value_holder_type,
            )
            value_type = value_holder_type.points_to
            store_type = mut_scope[-1]
            base_type_is_same = type(value_type) == type(store_type)  # noqa: E721
            if base_type_is_same and not is_types_same(
                value_type,
                store_type,
                strategy="strict-same-type",
            ):
                msg = f"\nStorage and value type mismatch at {operator.location}. Holder has type {value_holder_type}, which is {value_type} but tried to store {store_type}.\n\nMismatch: {store_type} != {value_type}\n[write-store-type-mismatch]"
                raise ValueError(msg)
        case OperatorType.LOAD_PARAM_ARGUMENT:
            scope.raise_for_enough_arguments(operator, required_args=1)
            scope.consume_n_arguments(1)
        case OperatorType.MEMORY_VARIABLE_READ:
            scope.raise_for_enough_arguments(operator, 1)
            ptr_t = scope.pop_type_from_stack()
            if not isinstance(ptr_t, PointerType):
                msg = f"Memory load (?>) is used to dereference an pointer but got {ptr_t} at {operator.location} (dereferencing-an-non-pointer-type)"
                raise TypeError(msg)

            revealed_type = ptr_t.points_to
            if isinstance(revealed_type, ArrayType):
                revealed_type = revealed_type.element_type
            scope.push_types(revealed_type)
        case OperatorType.PUSH_VARIABLE_VALUE:
            # TODO(@kirillzhosul): Should be refactored as consist of PUSH_VARIABLE_ADDRESS + MEMORY_VARIABLE_READ
            assert isinstance(operator.operand, str)
            varname = operator.operand
            variable = {**module.variables, **current_function.variables}[varname]

            # Track usages of each variable
            references_variables[varname] = variable

            memory_location = {
                VariableStorageClass.STACK: PointerMemoryLocation.STACK,
                VariableStorageClass.STATIC: PointerMemoryLocation.STATIC,
            }[variable.storage_class]

            revealed_type = variable.type
            if isinstance(revealed_type, ArrayType):
                revealed_type = revealed_type.element_type
            scope.push_types(revealed_type)
        case OperatorType.STACK_COPY:
            scope.raise_for_enough_arguments(operator, required_args=1)
            argument_type = scope.pop_type_from_stack()
            scope.push_types(argument_type, argument_type)
        case OperatorType.COMPARE_EQUALS | OperatorType.COMPARE_NOT_EQUALS:
            scope.raise_for_operator_arguments(
                operator,
                (I64Type, BoolType),
                (I64Type, BoolType),
            )
            scope.push_types(BoolType())
        case (
            OperatorType.COMPARE_LESS_EQUALS
            | OperatorType.COMPARE_LESS
            | OperatorType.COMPARE_GREATER_EQUALS
            | OperatorType.COMPARE_GREATER
        ):
            # TODO(@kirillzhosul): Generic comparison
            scope.raise_for_operator_arguments(
                operator,
                (I64Type,),
                (I64Type,),
            )
            scope.push_types(BoolType())
        case OperatorType.STACK_DROP:
            scope.raise_for_enough_arguments(operator, 1)
            scope.consume_n_arguments(1)
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
            scope.raise_for_operator_arguments(
                operator,
                *argument_types,
            )
            scope.push_types(I64Type())
        case OperatorType.STACK_SWAP:
            scope.raise_for_enough_arguments(operator, required_args=2)
            b, a = (
                scope.pop_type_from_stack(),
                scope.pop_type_from_stack(),
            )
            scope.push_types(b, a)

        case OperatorType.LOGICAL_OR | OperatorType.LOGICAL_AND:
            scope.raise_for_operator_arguments(
                operator,
                (BoolType,),
                (BoolType,),
            )
            scope.push_types(BoolType())
        case OperatorType.LOGICAL_NOT:
            scope.raise_for_operator_arguments(operator, (BoolType,))
            scope.push_types(BoolType())
        case (
            OperatorType.BITWISE_OR
            | OperatorType.BITWISE_AND
            | OperatorType.SHIFT_LEFT
            | OperatorType.SHIFT_RIGHT
            | OperatorType.BITWISE_XOR
        ):
            scope.raise_for_operator_arguments(
                operator,
                (I64Type,),
                (I64Type,),
            )
            scope.push_types(I64Type())

        case OperatorType.STATIC_TYPE_CAST:
            assert isinstance(operator.operand, Type)
            to_type_cast = operator.operand
            scope.raise_for_enough_arguments(operator, required_args=1)
            previous_type = scope.pop_type_from_stack()
            lint_typecast_same_type(
                on_lint_warning,
                t_from=previous_type,
                t_to=to_type_cast,
                at=operator.token.location,
            )
            scope.push_types(to_type_cast)
        case OperatorType.STRUCT_FIELD_OFFSET:
            scope.raise_for_enough_arguments(operator, required_args=1)
            struct_pointer_type = scope.pop_type_from_stack()
            assert isinstance(struct_pointer_type, PointerType), (
                f"Expected PUSH_STRUCT_FIELD_OFFSET to have structure pointer type on type stack but got {struct_pointer_type}"
            )

            struct_type = struct_pointer_type.points_to
            assert isinstance(operator.operand, tuple)
            _, struct_field = (
                operator.operand
            )  # TODO(@kirillzhosul): Checkout same struct
            assert isinstance(struct_field, str), (
                "Expected struct field as an string in operand"
            )
            assert isinstance(struct_type, StructureType), (
                f"Expected PUSH_STRUCT_FIELD_OFFSET to have structure type on type stack but got {struct_type}"
            )

            if struct_field not in struct_type.natural_fields:
                msg = (
                    f"Unknown field '{struct_field}' for known-structure {struct_type}"
                )
                raise ValueError(msg)

            scope.push_types(
                PointerType(points_to=struct_type.get_field_type(struct_field)),
            )

        case OperatorType.FUNCTION_CALL_FROM_STACK_POINTER:
            scope.raise_for_enough_arguments(operator, required_args=1)
            function_t = scope.pop_type_from_stack()
            assert isinstance(function_t, FunctionType)
            scope.raise_for_function_arguments(
                callee=function_t,
                caller=current_function,
                at=operator,
            )
            if not isinstance(function_t.return_type, VoidType):
                scope.push_types(function_t.return_type)
        case OperatorType.PUSH_FUNCTION_POINTER:
            assert isinstance(operator.operand, FunctionCallOperand)
            operand = operator.operand
            function = module.resolve_function_dependency(
                operand.module,
                operand.get_name(),
            )

            assert function is not None, (
                "Function existence must be resolved before typechecker stage!"
            )
            scope.push_types(
                FunctionType(
                    parameter_types=function.parameters,
                    return_type=function.return_type,
                ),
            )
        case _:
            assert_never(operator.type)

    return None


def _validate_retval_stack(
    function: Function,
    emulated_type_stack: Sequence[Type],
    return_hit_at: TokenLocation | None,
) -> None:
    _ = return_hit_at  # TODO(@kirillzhosul): Emit an proper warning
    if len(emulated_type_stack) > 1:
        msg = f"Ambiguous stack size at function end in {function.name} at {function.defined_at}"
        raise ValueError(msg)
    if not function.has_return_value():
        return
    if len(emulated_type_stack) == 0:
        raise ReturnValueMissingTypecheckError(owner=function)

    retval_t = emulated_type_stack[0]
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
