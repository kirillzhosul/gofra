"""Core AARCH64 MacOS codegen."""

from __future__ import annotations

from typing import IO, TYPE_CHECKING, assert_never

from gofra.codegen.backends.general import (
    CODEGEN_ENTRY_POINT_SYMBOL,
    CODEGEN_GOFRA_CONTEXT_LABEL,
    CODEGEN_INTRINSIC_TO_ASSEMBLY_OPS,
)
from gofra.consts import GOFRA_ENTRY_POINT
from gofra.parser.functions.function import Function
from gofra.parser.intrinsics import Intrinsic
from gofra.parser.operators import Operator, OperatorType

from ._context import AMD64CodegenContext
from .assembly import (
    call_function_block,
    drop_cells_from_stack,
    evaluate_conditional_block_on_stack_with_jump,
    function_begin_with_prologue,
    function_end_with_epilogue,
    initialize_static_data_section,
    load_memory_from_stack_arguments,
    perform_operation_onto_stack,
    pop_cells_from_stack_into_registers,
    push_integer_onto_stack,
    push_register_onto_stack,
    push_static_address_onto_stack,
    store_into_memory_from_stack_arguments,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from gofra.context import ProgramContext


def generate_amd64_windows_backend(
    fd: IO[str],
    program: ProgramContext,
) -> None:
    """AMD64 Linux code generation backend."""
    context = AMD64CodegenContext(fd=fd, strings={})

    context.fd.write("section .text\n")
    context.fd.write(f"global {CODEGEN_ENTRY_POINT_SYMBOL}\n")
    for func in program.functions.values():
        if not func.external_definition_link_to:
            continue
        context.fd.write(f"extern {func.external_definition_link_to}\n")
    amd64_windows_executable_functions(context, program)
    amd64_windows_program_entry_point(context)
    amd64_windows_data_section(context, program)


def amd64_linux_instruction_set(
    context: AMD64CodegenContext,
    operators: Sequence[Operator],
    program: ProgramContext,
    owner_function_name: str,
) -> None:
    """Write executable instructions from given operators."""
    for idx, operator in enumerate(operators):
        amd64_windows_operator_instructions(
            context,
            operator,
            program,
            idx,
            owner_function_name,
        )
        if operator.type == OperatorType.FUNCTION_RETURN:
            break


def amd64_windows_operator_instructions(
    context: AMD64CodegenContext,
    operator: Operator,
    program: ProgramContext,
    idx: int,
    owner_function_name: str,
) -> None:
    match operator.type:
        case OperatorType.INTRINSIC:
            amd64_windows_intrinsic_instructions(context, operator)
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
                context.write(f"jmp {label_to}")
            context.fd.write(f"{label}:\n")
        case OperatorType.PUSH_STRING:
            assert isinstance(operator.operand, str)
            push_static_address_onto_stack(
                context,
                segment=context.load_string(operator.token.text[1:-1]),
            )
            push_integer_onto_stack(context, value=len(operator.operand))
        case OperatorType.FUNCTION_CALL:
            assert isinstance(operator.operand, str)

            function = program.functions[operator.operand]
            function_name = function.external_definition_link_to or function.name
            call_function_block(
                context,
                function_name=function_name,
                abi_ffi_push_retval_onto_stack=function.abi_ffi_push_retval_onto_stack(),
                abi_ffi_arguments_count=function.abi_ffi_arguments_count(),
            )
        case OperatorType.FUNCTION_RETURN:
            function_end_with_epilogue(context)
        case _:
            assert_never(operator.type)


def amd64_windows_intrinsic_instructions(
    context: AMD64CodegenContext,
    operator: Operator,
) -> None:
    """Write executable body for intrinsic operation."""
    assert isinstance(operator.operand, Intrinsic)
    assert operator.type == OperatorType.INTRINSIC
    match operator.operand:
        case Intrinsic.DROP:
            drop_cells_from_stack(context, cells_count=1)
        case Intrinsic.COPY:
            pop_cells_from_stack_into_registers(context, "rax")
            push_register_onto_stack(context, "rax")
            push_register_onto_stack(context, "rax")
        case Intrinsic.SWAP:
            pop_cells_from_stack_into_registers(context, "rax", "rbx")
            push_register_onto_stack(context, "rax")
            push_register_onto_stack(context, "rbx")
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
            msg = "Syscall is prohibited on Windows target, use WINAPI."
            raise NotImplementedError(msg)
        case Intrinsic.MEMORY_LOAD:
            load_memory_from_stack_arguments(context)
        case Intrinsic.MEMORY_STORE:
            store_into_memory_from_stack_arguments(context)
        case Intrinsic.BREAKPOINT:
            raise NotImplementedError(operator)
        case _:
            assert_never(operator.operand)


def amd64_windows_executable_functions(
    context: AMD64CodegenContext,
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
        function_name = function.name
        if function == program.entry_point:
            function_name = "gofra_main"
        assert not function.is_global_linker_symbol or (
            not function.type_contract_in and not function.type_contract_out
        ), "Codegen does not supports global linker symbols that has type contracts"
        function_begin_with_prologue(
            context,
            function_name=function_name,
            as_global_linker_symbol=function.is_global_linker_symbol,
        )

        amd64_linux_instruction_set(context, function.source, program, function.name)
        function_end_with_epilogue(context)


def amd64_windows_program_entry_point(context: AMD64CodegenContext) -> None:
    """Write program entry, used to not segfault due to returning into protected system memory."""
    # This is an executable entry point
    function_begin_with_prologue(
        context,
        function_name="main",  # CODEGEN_ENTRY_POINT_SYMBOL
        as_global_linker_symbol=False,
    )

    # Prepare and execute main function
    call_function_block(
        context,
        function_name="gofra_main",  # GOFRA_ENTRY_POINT,
        abi_ffi_push_retval_onto_stack=False,
        abi_ffi_arguments_count=0,
    )

    # Call syscall to exit without accessing protected system memory.
    # `ret` into return-address will fail with segfault
    # ipc_syscall_linux(
    #    context,
    #    arguments_count=1,
    #    store_retval_onto_stack=False,
    #   injected_args=[
    #        AMD64_LINUX_EPILOGUE_EXIT_SYSCALL_NUMBER,
    #        AMD64_LINUX_EPILOGUE_EXIT_CODE,
    #    ],
    # )


def amd64_windows_data_section(
    context: AMD64CodegenContext,
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
