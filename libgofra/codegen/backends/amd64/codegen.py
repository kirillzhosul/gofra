"""Core AMD64 codegen."""

from __future__ import annotations

from typing import IO, TYPE_CHECKING, assert_never

from libgofra.codegen.abi import LinuxAMD64ABI
from libgofra.codegen.backends.amd64.executable_entry_point import (
    amd64_program_entry_point,
)
from libgofra.codegen.backends.general import CODEGEN_GOFRA_CONTEXT_LABEL
from libgofra.codegen.sections._factory import SectionType
from libgofra.hir.operator import FunctionCallOperand, Operator, OperatorType
from libgofra.hir.variable import VariableStorageClass
from libgofra.linker.entry_point import LINKER_EXPECTED_ENTRY_POINT

from ._context import AMD64CodegenContext
from .assembly import (
    drop_cells_from_stack,
    evaluate_conditional_block_on_stack_with_jump,
    function_call,
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
from .static_data_section import initialize_static_data_section
from .subroutines import (
    function_begin_with_prologue,
    function_end_with_epilogue,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from libgofra.codegen.config import CodegenConfig
    from libgofra.hir.function import Function
    from libgofra.hir.module import Module
    from libgofra.targets.target import Target


class AMD64CodegenBackend:
    target: Target
    module: Module

    def __init__(
        self,
        target: Target,
        module: Module,
        fd: IO[str],
        on_warning: Callable[[str], None],
        config: CodegenConfig,
    ) -> None:
        assert target.operating_system == "Linux"

        self.target = target
        self.module = module
        self.context = AMD64CodegenContext(
            on_warning=on_warning,
            fd=fd,
            strings={},
            target=self.target,
            abi=LinuxAMD64ABI(),
            config=config,  # TODO: DWARF CFI / Alignment
        )

    def emit(self) -> None:
        """AMD64 code generation backend."""
        self.context.section(SectionType.INSTRUCTIONS)
        amd64_executable_functions(self.context, self.module)
        if self.module.entry_point_ref:
            amd64_program_entry_point(
                self.context,
                LINKER_EXPECTED_ENTRY_POINT,
                self.module.entry_point_ref,
                self.target,
            )
        amd64_data_section(self.context, self.module)


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


def _push_variable_address(
    context: AMD64CodegenContext,
    owner_function: Function,
    variable: str,
) -> None:
    if variable in owner_function.variables:
        # Local variable
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

    # Global variable access
    push_static_address_onto_stack(context, variable)


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
            _push_variable_address(context, owner_function, variable=operator.operand)
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
            push_static_address_onto_stack(
                context,
                segment=context.load_string(string_raw),
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
            | OperatorType.LOGICAL_NOT
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
        case OperatorType.PUSH_VARIABLE_VALUE:
            assert isinstance(operator.operand, str)
            _push_variable_address(context, owner_function, variable=operator.operand)
            load_memory_from_stack_arguments(context)
        case OperatorType.LOAD_PARAM_ARGUMENT:
            assert isinstance(operator.operand, str)
            _push_variable_address(context, owner_function, variable=operator.operand)
            # swap
            pop_cells_from_stack_into_registers(context, "rax", "rbx")
            push_register_onto_stack(context, "rax")
            push_register_onto_stack(context, "rbx")
            store_into_memory_from_stack_arguments(context)
        case OperatorType.MEMORY_VARIABLE_WRITE:
            store_into_memory_from_stack_arguments(context)
        case OperatorType.DEBUGGER_BREAKPOINT:
            context.write("int3")
        case OperatorType.STRUCT_FIELD_OFFSET:
            assert isinstance(operator.operand, tuple)
            struct, field = operator.operand
            field_offset = struct.get_field_offset(field)
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
        case OperatorType.INLINE_RAW_ASM:
            assert isinstance(operator.operand, str)
            context.write(*operator.operand.splitlines())
        case OperatorType.COMPILE_TIME_ERROR:
            ...  # Linter / typechecker
        case OperatorType.PUSH_FUNCTION_POINTER:
            raise NotImplementedError(operator)
        case OperatorType.FUNCTION_CALL_FROM_STACK_POINTER:
            raise NotImplementedError(operator)
        case _:
            assert_never(operator.type)


def amd64_executable_functions(
    context: AMD64CodegenContext,
    program: Module,
) -> None:
    """Define all executable functions inside final executable with their executable body respectfully.

    Provides an prolog and epilogue.
    """
    for function in program.executable_functions:
        function_begin_with_prologue(
            context,
            local_variables=function.variables,
            arguments_count=len(function.parameters),
            function_name=function.name,
            preserve_frame=True,
            as_global_linker_symbol=function.is_public,
        )

        amd64_instruction_set(context, function.operators, program, function)

        # TODO(@kirillzhosul): This is included even after explicit return after end
        function_end_with_epilogue(
            context,
            has_preserved_frame=True,
            return_type=function.return_type,
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
