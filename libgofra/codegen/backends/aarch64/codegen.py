"""Core AARCH64 MacOS codegen."""

from __future__ import annotations

from typing import IO, TYPE_CHECKING, assert_never

from libgofra.codegen.abi import DarwinAARCH64ABI
from libgofra.codegen.backends.aarch64._context import AARCH64CodegenContext
from libgofra.codegen.backends.aarch64.abi_call_convention import (
    function_abi_call_by_symbol,
)
from libgofra.codegen.backends.aarch64.executable_entry_point import (
    aarch64_program_entry_point,
)
from libgofra.codegen.backends.aarch64.frame import (
    push_local_variable_address_from_frame_offset,
)
from libgofra.codegen.backends.aarch64.primitive_instructions import (
    debugger_breakpoint_trap,
    drop_stack_slots,
    evaluate_conditional_block_on_stack_with_jump,
    load_memory_from_stack_arguments,
    perform_operation_onto_stack,
    pop_cells_from_stack_into_registers,
    push_float_onto_stack,
    push_integer_onto_stack,
    push_register_onto_stack,
    push_static_address_onto_stack,
    store_into_memory_from_stack_arguments,
)
from libgofra.codegen.backends.aarch64.static_data_section import (
    aarch64_data_section,
)
from libgofra.codegen.backends.aarch64.subroutines import (
    function_begin_with_prologue,
    function_end_with_epilogue,
    function_return,
)
from libgofra.codegen.backends.aarch64.svc_syscall import ipc_aarch64_syscall
from libgofra.codegen.backends.general import CODEGEN_GOFRA_CONTEXT_LABEL
from libgofra.codegen.sections import SectionType
from libgofra.consts import GOFRA_ENTRY_POINT
from libgofra.hir.operator import Operator, OperatorType
from libgofra.hir.variable import VariableStorageClass
from libgofra.linker.entry_point import LINKER_EXPECTED_ENTRY_POINT

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from libgofra.hir.function import Function
    from libgofra.hir.module import Module
    from libgofra.targets.target import Target


class AARCH64CodegenBackend:
    target: Target
    module: Module
    context: AARCH64CodegenContext

    def __init__(
        self,
        target: Target,
        module: Module,
        fd: IO[str],
        on_warning: Callable[[str], None],
    ) -> None:
        self.target = target
        self.module = module
        self.context = AARCH64CodegenContext(
            on_warning=on_warning,
            fd=fd,
            abi=DarwinAARCH64ABI(),
            target=self.target,
        )

    def emit(self) -> None:
        """AARCH64 code generation backend."""
        # Executable section with instructions only (pure_instructions)
        self.context.section(SectionType.INSTRUCTIONS)

        aarch64_executable_functions(self.context, self.module)
        if GOFRA_ENTRY_POINT in self.module.functions:
            # TODO(@kirillzhosul): Treat entry point as separate concept, and probably treat as an warning for executables
            entry_point = self.module.functions[GOFRA_ENTRY_POINT]
            aarch64_program_entry_point(
                self.context,
                system_entry_point_name=LINKER_EXPECTED_ENTRY_POINT,
                entry_point=entry_point,
                target=self.target,
            )
        aarch64_data_section(self.context, self.module)


def aarch64_instruction_set(
    context: AARCH64CodegenContext,
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


def _push_variable_address(
    context: AARCH64CodegenContext,
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
    push_static_address_onto_stack(context, variable)


def aarch64_operator_instructions(
    context: AARCH64CodegenContext,
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
                context.write(f"b {label_to}")
            context.fd.write(f"{label}:\n")
        case OperatorType.PUSH_STRING:
            assert isinstance(operator.operand, str)
            string_raw = str(operator.token.text[1:-1])
            push_static_address_onto_stack(
                context,
                segment=context.load_string(string_raw),
            )
        case OperatorType.FUNCTION_RETURN:
            function_return(
                context,
                has_preserved_frame=True,
                return_type=owner_function.return_type,
            )
        case OperatorType.FUNCTION_CALL:
            assert isinstance(operator.operand, str)

            assert operator.operand in program.functions, operator.location
            function = program.functions[operator.operand]

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
            debugger_breakpoint_trap(context, number=1)
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
                context.write(f"add X0, X0, #{field_offset}")
                push_register_onto_stack(context, "X0")
        case _:
            assert_never(operator.type)


def aarch64_executable_functions(
    context: AARCH64CodegenContext,
    program: Module,
) -> None:
    """Define all executable functions inside final executable with their executable body respectfully.

    Provides an prolog and epilogue.
    """
    for function in program.executable_functions:
        function_begin_with_prologue(
            context,
            name=function.name,
            local_variables=function.variables,
            global_name=function.name if function.is_global else None,
            preserve_frame=True,
            parameters=function.parameters,
        )

        aarch64_instruction_set(context, function.operators, program, function)

        # TODO(@kirillzhosul): This is included even after explicit return after end
        function_end_with_epilogue(
            context,
            has_preserved_frame=True,
            return_type=function.return_type,
            is_early_return=False,
        )
