from collections.abc import Sequence
from typing import TYPE_CHECKING, assert_never

from libgofra.codegen.backends.aarch64.abi_call_convention import (
    function_abi_call_by_symbol,
    function_abi_call_from_register,
)
from libgofra.codegen.backends.aarch64.frame import (
    push_local_variable_address_from_frame_offset,
)
from libgofra.codegen.backends.aarch64.primitive_instructions import (
    AddressingMode,
    drop_stack_slots,
    evaluate_conditional_block_on_stack_with_jump,
    load_memory_from_stack_arguments,
    perform_operation_onto_stack,
    place_software_trap,
    pop_cells_from_stack_into_registers,
    push_address_of_label_onto_stack,
    push_float_onto_stack,
    push_integer_onto_stack,
    push_register_onto_stack,
    store_into_memory_from_stack_arguments,
)
from libgofra.codegen.backends.aarch64.subroutines import function_return
from libgofra.codegen.backends.aarch64.svc_syscall import ipc_aarch64_syscall
from libgofra.codegen.backends.general import CODEGEN_GOFRA_CONTEXT_LABEL
from libgofra.hir.function import Function
from libgofra.hir.module import Module
from libgofra.hir.operator import FunctionCallOperand, Operator, OperatorType
from libgofra.hir.variable import VariableStorageClass
from libgofra.types.composite.function import FunctionType

if TYPE_CHECKING:
    from libgofra.codegen.backends.aarch64.codegen import AARCH64CodegenBackend
    from libgofra.codegen.backends.aarch64.registers import AARCH64_GP_REGISTERS


def _push_variable_address(
    context: "AARCH64CodegenBackend",
    owner_function: Function,
    variable: str,
) -> None:
    if variable in owner_function.variables:
        hir_local_variable = owner_function.variables[variable]
        assert hir_local_variable.is_function_scope
        if hir_local_variable.storage_class != VariableStorageClass.STACK:
            msg = "Non stack local variables storage class is not implemented yet"
            raise NotImplementedError(msg)
        push_local_variable_address_from_frame_offset(
            context,
            owner_function.variables,
            variable,
        )
        return

    # Global variable or memory
    push_address_of_label_onto_stack(context, label=variable)


def aarch64_instruction_set(
    context: "AARCH64CodegenBackend",
    operators: Sequence[Operator],
    program: Module,
    owner_function: Function,
) -> None:
    """Write executable instructions from given operators."""
    for idx, operator in enumerate(operators):
        aarch64_operator_instructions(
            context,
            operator,
            program,
            idx,
            owner_function,
        )


def aarch64_operator_instructions(
    context: "AARCH64CodegenBackend",
    operator: Operator,
    program: Module,
    idx: int,
    owner_function: Function,
) -> None:
    # TODO(@kirillzhosul): Assumes Apple aapcs64
    match operator.type:
        case OperatorType.PUSH_VARIABLE_ADDRESS:
            assert isinstance(operator.operand, str)
            _push_variable_address(context, owner_function, variable=operator.operand)
        case OperatorType.PUSH_INTEGER:
            assert isinstance(operator.operand, int)
            push_integer_onto_stack(context, operator.operand)
        case OperatorType.PUSH_FLOAT:
            assert isinstance(operator.operand, float)
            push_float_onto_stack(context, operator.operand)
        case OperatorType.CONDITIONAL_DO | OperatorType.CONDITIONAL_IF:
            assert isinstance(operator.jumps_to_operator_idx, int)
            label = CODEGEN_GOFRA_CONTEXT_LABEL % (
                owner_function.name,
                operator.jumps_to_operator_idx,
            )
            evaluate_conditional_block_on_stack_with_jump(context, label)
        case (
            OperatorType.CONDITIONAL_END
            | OperatorType.CONDITIONAL_WHILE
            | OperatorType.CONDITIONAL_FOR
        ):
            # This also should be refactored into `assembly` layer
            label = CODEGEN_GOFRA_CONTEXT_LABEL % (owner_function.name, idx)
            if isinstance(operator.jumps_to_operator_idx, int):
                label_to = CODEGEN_GOFRA_CONTEXT_LABEL % (
                    owner_function.name,
                    operator.jumps_to_operator_idx,
                )
                context.instruction(f"b {label_to}")
            context.label(label)
        case OperatorType.PUSH_STRING:
            assert isinstance(operator.operand, str)
            string_raw = str(operator.token.text[1:-1])
            label = context.load_string(string_raw)
            push_address_of_label_onto_stack(context, label)
        case OperatorType.FUNCTION_RETURN:
            function_return(
                context,
                has_preserved_frame=True,
                return_type=owner_function.return_type,
            )
        case OperatorType.FUNCTION_CALL:
            assert isinstance(operator.operand, FunctionCallOperand)

            function = program.resolve_function_dependency(
                operator.operand.module,
                operator.operand.get_name(),
            )
            assert function is not None, (
                f"Cannot find function symbol `{operator.operand.get_name()}` in module '{operator.operand.module}' (current: {program.path}), will emit linkage error"
            )

            function_abi_call_by_symbol(
                context,
                name=function.name,
                parameters=function.parameters,
                return_type=function.return_type,
                call_convention="apple_aapcs64",
            )
        case OperatorType.STATIC_TYPE_CAST:
            # Skip that as it is typechecker only.
            pass
        case OperatorType.STACK_DROP:
            drop_stack_slots(context, slots_count=1)
        case OperatorType.STACK_COPY:
            pop_cells_from_stack_into_registers(context, "X0")
            push_register_onto_stack(context, "X0")
            push_register_onto_stack(context, "X0")
        case OperatorType.STACK_SWAP:
            pop_cells_from_stack_into_registers(context, "X0", "X1")
            push_register_onto_stack(context, "X0")
            push_register_onto_stack(context, "X1")
        case (
            OperatorType.ARITHMETIC_MINUS
            | OperatorType.ARITHMETIC_PLUS
            | OperatorType.ARITHMETIC_MULTIPLY
            | OperatorType.ARITHMETIC_DIVIDE
            | OperatorType.ARITHMETIC_MODULUS
            | OperatorType.COMPARE_NOT_EQUALS
            | OperatorType.COMPARE_GREATER_EQUALS
            | OperatorType.COMPARE_LESS_EQUALS
            | OperatorType.COMPARE_LESS
            | OperatorType.COMPARE_GREATER
            | OperatorType.COMPARE_EQUALS
            | OperatorType.LOGICAL_NOT
            | OperatorType.LOGICAL_AND
            | OperatorType.LOGICAL_OR
            | OperatorType.BITWISE_AND
            | OperatorType.BITWISE_OR
            | OperatorType.SHIFT_LEFT
            | OperatorType.SHIFT_RIGHT
            | OperatorType.BITWISE_XOR
        ):
            perform_operation_onto_stack(
                context,
                operation=operator.type,
            )
        case OperatorType.SYSCALL:
            assert isinstance(operator.operand, int)
            ipc_aarch64_syscall(
                context,
                arguments_count=operator.operand,
                store_retval_onto_stack=True,
                injected_args=None,
            )
        case OperatorType.MEMORY_VARIABLE_READ:
            load_memory_from_stack_arguments(context)
        case OperatorType.MEMORY_VARIABLE_WRITE:
            store_into_memory_from_stack_arguments(context)
        case OperatorType.PUSH_VARIABLE_VALUE:
            assert isinstance(operator.operand, str)

            # TODO(@kirillzhosul): This was merged from two operations - must be refactored (and also optimized)
            _push_variable_address(context, owner_function, operator.operand)
            load_memory_from_stack_arguments(context)
        case OperatorType.LOAD_PARAM_ARGUMENT:
            assert isinstance(operator.operand, str)
            # TODO(@kirillzhosul): This was merged from two operations - must be refactored (and also optimized)
            _push_variable_address(context, owner_function, operator.operand)

            # swap stack
            pop_cells_from_stack_into_registers(context, "X0", "X1")
            push_register_onto_stack(context, "X0")
            push_register_onto_stack(context, "X1")

            store_into_memory_from_stack_arguments(context)

        case OperatorType.DEBUGGER_BREAKPOINT:
            place_software_trap(
                context,
                code=0xDEAD,
            )
        case OperatorType.INLINE_RAW_ASM:
            assert isinstance(operator.operand, str)
            for line in operator.operand.splitlines():
                context.instruction(line)
        case OperatorType.STRUCT_FIELD_OFFSET:
            assert isinstance(operator.operand, tuple)
            struct, field = operator.operand
            field_offset = struct.get_field_offset(field)
            if field_offset:
                # only relatable as operation is pointer is not already at first structure field
                pop_cells_from_stack_into_registers(
                    context,
                    "X0",
                )  # struct pointer (*struct)
                context.instruction(f"add X0, X0, #{field_offset}")
                push_register_onto_stack(context, "X0")
        case OperatorType.COMPILE_TIME_ERROR:
            ...  # Linter / typechecker
        case OperatorType.FUNCTION_CALL_FROM_STACK_POINTER:
            assert isinstance(operator.operand, FunctionType)
            call_like = operator.operand
            ptr_reg: AARCH64_GP_REGISTERS = "X10"
            pop_cells_from_stack_into_registers(context, ptr_reg)
            function_abi_call_from_register(
                context,
                register=ptr_reg,
                parameters=call_like.parameters,
                return_type=call_like.return_type,
                call_convention="apple_aapcs64",
            )
        case OperatorType.PUSH_FUNCTION_POINTER:
            assert isinstance(operator.operand, FunctionCallOperand)
            calee = program.resolve_function_dependency(
                operator.operand.module,
                operator.operand.get_name(),
            )
            assert calee

            if calee.is_external:
                addressing_mode = AddressingMode.EXTERNAL
            elif calee.enclosed_in_parent == owner_function:
                addressing_mode = AddressingMode.NEAR
            else:
                addressing_mode = AddressingMode.PAGE

            push_address_of_label_onto_stack(
                context,
                label=calee.name,
                temp_register="X0",
                mode=addressing_mode,
            )
        case _:
            assert_never(operator.type)
