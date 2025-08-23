"""Core AARCH64 MacOS codegen."""

from __future__ import annotations

from typing import IO, TYPE_CHECKING, assert_never

from gofra.codegen.backends.aarch64_macos._context import AARCH64CodegenContext
from gofra.codegen.backends.aarch64_macos.assembly import (
    call_function_block,
    drop_cells_from_stack,
    evaluate_conditional_block_on_stack_with_jump,
    function_begin_with_prologue,
    function_end_with_epilogue,
    initialize_static_data_section,
    ipc_syscall_macos,
    load_memory_from_stack_arguments,
    perform_operation_onto_stack,
    pop_cells_from_stack_into_registers,
    push_integer_onto_stack,
    push_register_onto_stack,
    push_static_address_onto_stack,
    store_into_memory_from_stack_arguments,
)
from gofra.codegen.backends.aarch64_macos.registers import (
    AARCH64_MACOS_EPILOGUE_EXIT_CODE,
    AARCH64_MACOS_EPILOGUE_EXIT_SYSCALL_NUMBER,
)
from gofra.codegen.backends.general import (
    CODEGEN_ENTRY_POINT_SYMBOL,
    CODEGEN_GOFRA_CONTEXT_LABEL,
    CODEGEN_INTRINSIC_TO_ASSEMBLY_OPS,
)
from gofra.consts import GOFRA_ENTRY_POINT
from gofra.parser.functions.function import Function
from gofra.parser.intrinsics import Intrinsic
from gofra.parser.operators import Operator, OperatorType

if TYPE_CHECKING:
    from collections.abc import Sequence

    from gofra.context import ProgramContext


def generate_aarch64_macos_backend(
    fd: IO[str],
    program: ProgramContext,
) -> None:
    """AARCH64 MacOS code generation backend."""
    context = AARCH64CodegenContext(fd=fd, strings={})

    aarch64_macos_executable_functions(context, program)
    aarch64_macos_program_entry_point(context)
    aarch64_macos_data_section(context, program)


def aarch64_macos_instruction_set(
    context: AARCH64CodegenContext,
    operators: Sequence[Operator],
    program: ProgramContext,
    owner_function_name: str,
) -> None:
    """Write executable instructions from given operators."""
    for idx, operator in enumerate(operators):
        aarch64_macos_operator_instructions(
            context,
            operator,
            program,
            idx,
            owner_function_name,
        )
        if operator.type == OperatorType.FUNCTION_RETURN:
            break


def aarch64_macos_operator_instructions(
    context: AARCH64CodegenContext,
    operator: Operator,
    program: ProgramContext,
    idx: int,
    owner_function_name: str,
) -> None:
    match operator.type:
        case OperatorType.INTRINSIC:
            aarch64_macos_intrinsic_instructions(context, operator)
        case OperatorType.PUSH_MEMORY_POINTER:
            assert isinstance(operator.operand, str)
            push_static_address_onto_stack(context, operator.operand)
        case OperatorType.PUSH_INTEGER:
            assert isinstance(operator.operand, int)
            push_integer_onto_stack(context, operator.operand)
        case OperatorType.DO | OperatorType.IF:
            assert isinstance(operator.jumps_to_operator_idx, int)
            label = CODEGEN_GOFRA_CONTEXT_LABEL % (
                owner_function_name,
                operator.jumps_to_operator_idx,
            )
            evaluate_conditional_block_on_stack_with_jump(context, label)
        case OperatorType.END | OperatorType.WHILE:
            # This also should be refactored into `assembly` layer
            label = CODEGEN_GOFRA_CONTEXT_LABEL % (owner_function_name, idx)
            if isinstance(operator.jumps_to_operator_idx, int):
                label_to = CODEGEN_GOFRA_CONTEXT_LABEL % (
                    owner_function_name,
                    operator.jumps_to_operator_idx,
                )
                context.write(f"b {label_to}")
            context.fd.write(f"{label}:\n")
        case OperatorType.PUSH_STRING:
            assert isinstance(operator.operand, str)
            string_raw = str(operator.token.text[1:-1])
            push_static_address_onto_stack(
                context,
                segment=context.load_string(string_raw),
            )
            push_integer_onto_stack(context, value=len(string_raw))
        case OperatorType.FUNCTION_RETURN:
            function_end_with_epilogue(context)
        case OperatorType.FUNCTION_CALL:
            assert isinstance(operator.operand, str)

            function = program.functions[operator.operand]
            call_function_block(
                context,
                function_name=function.name,
                abi_ffi_push_retval_onto_stack=function.abi_ffi_push_retval_onto_stack(),
                abi_ffi_arguments_count=len(function.type_contract_in),
            )

        case _:
            assert_never(operator.type)


def aarch64_macos_intrinsic_instructions(
    context: AARCH64CodegenContext,
    operator: Operator,
) -> None:
    """Write executable body for intrinsic operation."""
    assert isinstance(operator.operand, Intrinsic)
    assert operator.type == OperatorType.INTRINSIC
    match operator.operand:
        case Intrinsic.DROP:
            drop_cells_from_stack(context, cells_count=1)
        case Intrinsic.COPY:
            pop_cells_from_stack_into_registers(context, "X0")
            push_register_onto_stack(context, "X0")
            push_register_onto_stack(context, "X0")
        case Intrinsic.SWAP:
            pop_cells_from_stack_into_registers(context, "X0", "X1")
            push_register_onto_stack(context, "X0")
            push_register_onto_stack(context, "X1")
        case (
            Intrinsic.PLUS
            | Intrinsic.MINUS
            | Intrinsic.MULTIPLY
            | Intrinsic.DIVIDE
            | Intrinsic.MODULUS
            | Intrinsic.INCREMENT
            | Intrinsic.DECREMENT
            | Intrinsic.NOT_EQUAL
            | Intrinsic.GREATER_EQUAL_THAN
            | Intrinsic.LESS_EQUAL_THAN
            | Intrinsic.LESS_THAN
            | Intrinsic.GREATER_THAN
            | Intrinsic.EQUAL
        ):
            perform_operation_onto_stack(
                context,
                operation=CODEGEN_INTRINSIC_TO_ASSEMBLY_OPS[operator.operand],
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
            assert operator.syscall_optimization_injected_args is None, "TODO: Optimize"
            ipc_syscall_macos(
                context,
                arguments_count=operator.get_syscall_arguments_count() - 1,
                store_retval_onto_stack=not operator.syscall_optimization_omit_result,
                injected_args=None,
            )
        case Intrinsic.MEMORY_LOAD:
            load_memory_from_stack_arguments(context)
        case Intrinsic.MEMORY_STORE:
            store_into_memory_from_stack_arguments(context)
        case _:
            assert_never(operator.operand)


def aarch64_macos_executable_functions(
    context: AARCH64CodegenContext,
    program: ProgramContext,
) -> None:
    """Define all executable functions inside final executable with their executable body respectuflly.

    Provides an prolog and epilogue.
    """
    # Define only function that contains anything to execute
    functions = filter(
        Function.has_executable_body,
        [*program.functions.values(), program.entry_point],
    )
    for function in functions:
        assert not function.is_global_linker_symbol or (
            not function.type_contract_in and not function.type_contract_out
        ), "Codegen does not supports global linker symbols that has type contracts"
        function_begin_with_prologue(
            context,
            function_name=function.name,
            as_global_linker_symbol=function.is_global_linker_symbol,
        )

        aarch64_macos_instruction_set(context, function.source, program, function.name)

        # TODO(@kirillzhosul): This is included even after explicit return after end
        function_end_with_epilogue(context)


def aarch64_macos_program_entry_point(context: AARCH64CodegenContext) -> None:
    """Write program entry, used to not segfault due to returning into protected system memory."""
    # This is an executable entry point
    function_begin_with_prologue(
        context,
        function_name=CODEGEN_ENTRY_POINT_SYMBOL,
        as_global_linker_symbol=True,
    )

    # Prepare and execute main function
    call_function_block(
        context,
        function_name=GOFRA_ENTRY_POINT,
        abi_ffi_push_retval_onto_stack=False,
        abi_ffi_arguments_count=0,
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


def aarch64_macos_data_section(
    context: AARCH64CodegenContext,
    program: ProgramContext,
) -> None:
    """Write program static data section filled with static strings and memory blobs."""
    initialize_static_data_section(
        context,
        static_data_section=[
            *context.strings.items(),
            *program.memories.items(),
        ],
    )
