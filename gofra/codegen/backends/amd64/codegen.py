"""Core AMD64 codegen."""

from __future__ import annotations

from typing import IO, TYPE_CHECKING, assert_never

from gofra.codegen.abi import LinuxAMD64ABI
from gofra.codegen.backends.general import CODEGEN_GOFRA_CONTEXT_LABEL
from gofra.consts import GOFRA_ENTRY_POINT
from gofra.hir.operator import Operator, OperatorType
from gofra.hir.variable import VariableStorageClass
from gofra.linker.entry_point import LINKER_EXPECTED_ENTRY_POINT
from gofra.types.primitive.void import VoidType
from gofra.types.primitive.integers import I64Type

from ._context import AMD64CodegenContext
from .assembly import (
    drop_cells_from_stack,
    evaluate_conditional_block_on_stack_with_jump,
    function_begin_with_prologue,
    function_call,
    function_end_with_epilogue,
    initialize_static_data_section,
    ipc_syscall_linux,
    load_memory_from_stack_arguments,
    perform_operation_onto_stack,
    pop_cells_from_stack_into_registers,
    push_integer_onto_stack,
    push_local_variable_address_from_frame_offset,
    push_register_onto_stack,
    push_static_address_onto_stack,
    store_into_memory_from_stack_arguments,
)
from .registers import (
    AMD64_LINUX_EPILOGUE_EXIT_CODE,
    AMD64_LINUX_EPILOGUE_EXIT_SYSCALL_NUMBER,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from gofra.hir.function import Function
    from gofra.hir.module import Module
    from gofra.targets.target import Target


def generate_amd64_backend(
    fd: IO[str],
    program: Module,
    target: Target,
) -> None:
    """AMD64 code generation backend."""
    match (target.architecture, target.operating_system):
        case ("AMD64", "Linux"):
            abi = LinuxAMD64ABI()
        case _:
            msg = f"Unknown ABI for {target.architecture}x{target.operating_system}"
            raise ValueError(msg)

    context = AMD64CodegenContext(fd=fd, strings={}, target=target, abi=abi)

    amd64_executable_functions(context, program)
    if GOFRA_ENTRY_POINT in program.functions:
        entry_point = program.functions[GOFRA_ENTRY_POINT]
        amd64_program_entry_point(context, entry_point)
    amd64_data_section(context, program)


def amd64_instruction_set(
    context: AMD64CodegenContext,
    operators: Sequence[Operator],
    program: Module,
    owner_function: Function,
) -> None:
    """Write executable instructions from given operators."""
    for idx, operator in enumerate(operators):
        amd64_operator_instructions(
            context,
            operator,
            program,
            idx,
            owner_function,
        )


def amd64_operator_instructions(
    context: AMD64CodegenContext,
    operator: Operator,
    program: Module,
    idx: int,
    owner_function: Function,
) -> None:
    match operator.type:
        case OperatorType.PUSH_VARIABLE_ADDRESS:
            assert isinstance(operator.operand, str)

            variable = operator.operand
            if variable in owner_function.variables:
                # Local variable
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

            # Global variable access
            push_static_address_onto_stack(context, variable)
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
                context.write(f"jmp {label_to}")
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
        case OperatorType.FUNCTION_CALL:
            assert isinstance(operator.operand, str)

            function = program.functions[operator.operand]
            function_call(
                context,
                name=function.name,
                type_contract_in=function.parameters,
                type_contract_out=function.return_type,
            )
        case OperatorType.FUNCTION_RETURN:
            function_end_with_epilogue(
                context,
                has_preserved_frame=True,
                return_type=owner_function.return_type,
            )
        case OperatorType.STATIC_TYPE_CAST:
            # Skip that as it is typechecker only.
            pass
        case OperatorType.STACK_DROP:
            drop_cells_from_stack(context, cells_count=1)
        case OperatorType.STACK_COPY:
            pop_cells_from_stack_into_registers(context, "rax")
            push_register_onto_stack(context, "rax")
            push_register_onto_stack(context, "rax")
        case OperatorType.STACK_SWAP:
            pop_cells_from_stack_into_registers(context, "rax", "rbx")
            push_register_onto_stack(context, "rax")
            push_register_onto_stack(context, "rbx")
        case (
            OperatorType.ARITHMETIC_PLUS
            | OperatorType.ARITHMETIC_MINUS
            | OperatorType.ARITHMETIC_MULTIPLY
            | OperatorType.ARITHMETIC_DIVIDE
            | OperatorType.ARITHMETIC_MODULUS
            | OperatorType.COMPARE_NOT_EQUALS
            | OperatorType.COMPARE_GREATER_EQUALS
            | OperatorType.COMPARE_LESS_EQUALS
            | OperatorType.COMPARE_LESS
            | OperatorType.COMPARE_GREATER
            | OperatorType.COMPARE_EQUALS
            | OperatorType.LOGICAL_OR
            | OperatorType.LOGICAL_AND
            | OperatorType.BITWISE_AND
            | OperatorType.BITWISE_OR
            | OperatorType.BITWISE_XOR
            | OperatorType.SHIFT_LEFT
            | OperatorType.SHIFT_RIGHT
        ):
            perform_operation_onto_stack(
                context,
                operation=operator.type,
            )
        case OperatorType.SYSCALL:
            if context.target.operating_system == "Windows":
                msg = "Usage of syscalls is discouraged on Windows, use WINAPI"
                raise ValueError(msg)
            assert isinstance(operator.operand, int)
            ipc_syscall_linux(
                context,
                arguments_count=operator.operand,
                store_retval_onto_stack=True,
                injected_args=[],
            )
        case OperatorType.MEMORY_VARIABLE_READ:
            load_memory_from_stack_arguments(context)
        case OperatorType.MEMORY_VARIABLE_WRITE:
            store_into_memory_from_stack_arguments(context)
        case OperatorType.DEBUGGER_BREAKPOINT:
            context.write("int3")
        case OperatorType.STRUCT_FIELD_OFFSET:
            assert isinstance(operator.operand, str)
            struct, field = operator.operand.split(".", maxsplit=1)
            field_offset = program.structures[struct].get_field_offset(field)
            if field_offset:
                # only relatable as operation is pointer is not already at first structure field
                pop_cells_from_stack_into_registers(
                    context,
                    "rax",
                )  # struct pointer (*struct)
                context.write(f"addq ${field_offset}, %rax")
                push_register_onto_stack(context, "rax")
        case OperatorType.PUSH_FLOAT:
            msg = "FPU is not implemented on amd64"
            raise ValueError(msg)
        case _:
            assert_never(operator.type)


def amd64_executable_functions(
    context: AMD64CodegenContext,
    program: Module,
) -> None:
    """Define all executable functions inside final executable with their executable body respectfully.

    Provides an prolog and epilogue.
    """
    functions = filter(
        lambda f: not f.is_external,
        program.functions.values(),
    )
    for function in functions:
        function_begin_with_prologue(
            context,
            local_variables=function.variables,
            arguments_count=function.arguments_count,
            function_name=function.name,
            preserve_frame=True,
            as_global_linker_symbol=function.is_global,
        )

        amd64_instruction_set(context, function.operators, program, function)

        # TODO(@kirillzhosul): This is included even after explicit return after end
        function_end_with_epilogue(
            context,
            has_preserved_frame=True,
            return_type=function.return_type,
        )


def amd64_program_entry_point(
    context: AMD64CodegenContext,
    entry_point: Function,
) -> None:
    """Write program entry, used to not segfault due to returning into protected system memory."""
    # This is an executable entry point
    function_begin_with_prologue(
        context,
        function_name=LINKER_EXPECTED_ENTRY_POINT,
        arguments_count=0,
        as_global_linker_symbol=True,
        preserve_frame=False,  # Unable to end with epilogue, but not required as this done via kernel OS
        local_variables={},
    )

    # Prepare and execute main function
    assert isinstance(entry_point.return_type, VoidType | I64Type)
    function_call(
        context,
        name=entry_point.name,
        type_contract_in=[],
        type_contract_out=entry_point.return_type,
    )

    if isinstance(entry_point.return_type, VoidType):
        assert context.target.operating_system != "Windows"
        # TODO!(@kirillzhosul): review exit code on Windows  # noqa: TD002, TD004
        # Call syscall to exit without accessing protected system memory.
        # `ret` into return-address will fail with segfault
        ipc_syscall_linux(
            context,
            arguments_count=1,
            store_retval_onto_stack=False,
            injected_args=[
                AMD64_LINUX_EPILOGUE_EXIT_SYSCALL_NUMBER,
                AMD64_LINUX_EPILOGUE_EXIT_CODE,
            ],
        )
    else:
        push_integer_onto_stack(context, AMD64_LINUX_EPILOGUE_EXIT_SYSCALL_NUMBER)
        ipc_syscall_linux(
            context,
            arguments_count=1,
            store_retval_onto_stack=False,
            injected_args=None,
        )

    function_end_with_epilogue(
        context=context,
        has_preserved_frame=False,
        execution_trap_instead_return=True,
        return_type=VoidType(),
    )


def amd64_data_section(
    context: AMD64CodegenContext,
    program: Module,
) -> None:
    """Write program static data section filled with static strings and memory blobs."""
    initialize_static_data_section(
        context,
        static_strings=context.strings,
        static_variables=program.variables,
    )
