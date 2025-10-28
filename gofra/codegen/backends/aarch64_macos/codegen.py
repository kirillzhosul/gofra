"""Core AARCH64 MacOS codegen."""

from __future__ import annotations

from typing import IO, TYPE_CHECKING, assert_never

from gofra.codegen.abi import DarwinAARCH64ABI
from gofra.codegen.backends.aarch64_macos._context import AARCH64CodegenContext
from gofra.codegen.backends.aarch64_macos.assembly import (
    debugger_breakpoint_trap,
    drop_stack_slots,
    evaluate_conditional_block_on_stack_with_jump,
    function_begin_with_prologue,
    function_call,
    function_end_with_epilogue,
    initialize_static_data_section,
    ipc_syscall_macos,
    load_memory_from_stack_arguments,
    perform_operation_onto_stack,
    pop_cells_from_stack_into_registers,
    push_integer_onto_stack,
    push_local_variable_address_from_frame_offset,
    push_register_onto_stack,
    push_static_address_onto_stack,
    store_into_memory_from_stack_arguments,
)
from gofra.codegen.backends.aarch64_macos.registers import (
    AARCH64_MACOS_EPILOGUE_EXIT_CODE,
    AARCH64_MACOS_EPILOGUE_EXIT_SYSCALL_NUMBER,
)
from gofra.codegen.backends.general import CODEGEN_GOFRA_CONTEXT_LABEL
from gofra.consts import GOFRA_ENTRY_POINT
from gofra.hir.operator import Operator, OperatorType
from gofra.hir.variable import VariableStorageClass
from gofra.linker.entry_point import LINKER_EXPECTED_ENTRY_POINT
from gofra.types.primitive.void import VoidType

if TYPE_CHECKING:
    from collections.abc import Sequence

    from gofra.hir.function import Function
    from gofra.hir.module import Module
    from gofra.targets.target import Target


def generate_aarch64_macos_backend(
    fd: IO[str],
    program: Module,
    target: Target,
) -> None:
    """AARCH64 MacOS code generation backend."""
    _ = target
    context = AARCH64CodegenContext(fd=fd, strings={}, abi=DarwinAARCH64ABI())

    # Executable section with instructions only (pure_instructions)
    context.write(".section __TEXT,__text,regular,pure_instructions")

    aarch64_macos_executable_functions(context, program)
    if GOFRA_ENTRY_POINT in program.functions:
        # TODO(@kirillzhosul): Treat entry point as separate concept, and probably treat as an warning for executables
        entry_point = program.functions[GOFRA_ENTRY_POINT]
        aarch64_macos_program_entry_point(context, entry_point)
    aarch64_macos_data_section(context, program)


def aarch64_macos_instruction_set(
    context: AARCH64CodegenContext,
    operators: Sequence[Operator],
    program: Module,
    owner_function: Function,
) -> None:
    """Write executable instructions from given operators."""
    for idx, operator in enumerate(operators):
        aarch64_macos_operator_instructions(
            context,
            operator,
            program,
            idx,
            owner_function,
        )
        if operator.type == OperatorType.FUNCTION_RETURN:
            break


def aarch64_macos_operator_instructions(
    context: AARCH64CodegenContext,
    operator: Operator,
    program: Module,
    idx: int,
    owner_function: Function,
) -> None:
    match operator.type:
        case OperatorType.PUSH_VARIABLE_ADDRESS:
            assert isinstance(operator.operand, str)

            if operator.operand in owner_function.variables:
                hir_local_variable = owner_function.variables[operator.operand]
                assert hir_local_variable.is_function_scope
                if hir_local_variable.storage_class != VariableStorageClass.STACK:
                    msg = (
                        "Non stack local variables storage class is not implemented yet"
                    )
                    raise NotImplementedError(msg)
                push_local_variable_address_from_frame_offset(
                    context,
                    owner_function.variables,
                    operator.operand,
                )
                return

            # Global variable or memory
            push_static_address_onto_stack(context, operator.operand)
        case OperatorType.PUSH_INTEGER:
            assert isinstance(operator.operand, int)
            push_integer_onto_stack(context, operator.operand)
        case OperatorType.CONDITIONAL_DO | OperatorType.CONDITIONAL_IF:
            assert isinstance(operator.jumps_to_operator_idx, int)
            label = CODEGEN_GOFRA_CONTEXT_LABEL % (
                owner_function.name,
                operator.jumps_to_operator_idx,
            )
            evaluate_conditional_block_on_stack_with_jump(context, label)
        case OperatorType.CONDITIONAL_END | OperatorType.CONDITIONAL_WHILE:
            # This also should be refactored into `assembly` layer
            label = CODEGEN_GOFRA_CONTEXT_LABEL % (owner_function.name, idx)
            if isinstance(operator.jumps_to_operator_idx, int):
                label_to = CODEGEN_GOFRA_CONTEXT_LABEL % (
                    owner_function.name,
                    operator.jumps_to_operator_idx,
                )
                context.write(f"b {label_to}")
            context.fd.write(f"{label}:\n")
        case OperatorType.PUSH_STRING:
            assert isinstance(operator.operand, str)
            string_raw = str(operator.token.text[1:-1])
            decoded_string = string_raw.encode().decode("unicode_escape")
            push_static_address_onto_stack(
                context,
                segment=context.load_string(string_raw),
            )
            push_integer_onto_stack(context, value=len(decoded_string))
        case OperatorType.FUNCTION_RETURN:
            function_end_with_epilogue(
                context,
                has_preserved_frame=True,
                return_type=owner_function.return_type,
            )
        case OperatorType.FUNCTION_CALL:
            assert isinstance(operator.operand, str)

            function = program.functions[operator.operand]

            function_call(
                context,
                name=function.name,
                type_contract_in=function.parameters,
                type_contract_out=function.return_type,
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
            ipc_syscall_macos(
                context,
                arguments_count=operator.operand,
                store_retval_onto_stack=True,
                injected_args=None,
            )
        case OperatorType.MEMORY_VARIABLE_READ:
            load_memory_from_stack_arguments(context)
        case OperatorType.MEMORY_VARIABLE_WRITE:
            store_into_memory_from_stack_arguments(context)
        case OperatorType.DEBUGGER_BREAKPOINT:
            debugger_breakpoint_trap(context, number=1)
        case OperatorType.STRUCT_FIELD_OFFSET:
            assert isinstance(operator.operand, str)
            struct, field = operator.operand.split(".", maxsplit=1)
            field_offset = program.structures[struct].get_field_offset(field)
            if field_offset:
                # only relatable as operation is pointer is not already at first structure field
                pop_cells_from_stack_into_registers(
                    context,
                    "X0",
                )  # struct pointer (*struct)
                context.write(f"add X0, X0, #{field_offset}")
                push_register_onto_stack(context, "X0")
        case _:
            assert_never(operator.type)


def aarch64_macos_executable_functions(
    context: AARCH64CodegenContext,
    program: Module,
) -> None:
    """Define all executable functions inside final executable with their executable body respectfully.

    Provides an prolog and epilogue.
    """
    for function in program.functions.values():
        function_begin_with_prologue(
            context,
            name=function.name,
            local_variables=function.variables,
            global_name=function.name if function.is_global else None,
            preserve_frame=True,
            arguments_count=function.arguments_count,
        )

        aarch64_macos_instruction_set(context, function.operators, program, function)

        # TODO(@kirillzhosul): This is included even after explicit return after end
        function_end_with_epilogue(
            context,
            has_preserved_frame=True,
            return_type=function.return_type,
        )


def aarch64_macos_program_entry_point(
    context: AARCH64CodegenContext,
    entry_point: Function,
) -> None:
    """Write program entry, used to not segfault due to returning into protected system memory."""
    # This is an executable entry point
    function_begin_with_prologue(
        context,
        name=LINKER_EXPECTED_ENTRY_POINT,
        global_name=LINKER_EXPECTED_ENTRY_POINT,
        preserve_frame=False,  # Unable to end with epilogue, but not required as this done via kernel OS
        local_variables={},
        arguments_count=0,
    )

    # Prepare and execute main function
    assert isinstance(entry_point.return_type, VoidType)
    assert not entry_point.has_return_value()
    function_call(
        context,
        name=entry_point.name,
        type_contract_in=[],
        type_contract_out=VoidType(),
    )

    # Call syscall to exit without accessing protected system memory.
    # `ret` into return-address will fail with segfault
    ipc_syscall_macos(
        context,
        arguments_count=1,
        store_retval_onto_stack=False,
        injected_args=[
            AARCH64_MACOS_EPILOGUE_EXIT_CODE,
            AARCH64_MACOS_EPILOGUE_EXIT_SYSCALL_NUMBER,
        ],
    )

    function_end_with_epilogue(
        context=context,
        has_preserved_frame=False,
        execution_trap_instead_return=True,
        return_type=VoidType(),
    )


def aarch64_macos_data_section(
    context: AARCH64CodegenContext,
    program: Module,
) -> None:
    """Write program static data section filled with static strings and memory blobs."""
    initialize_static_data_section(
        context,
        static_strings=context.strings,
        static_variables=program.variables,
    )
