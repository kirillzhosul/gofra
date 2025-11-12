"""Assembly abstraction layer that hides declarative assembly OPs into functions that generates that for you."""

from __future__ import annotations

from typing import TYPE_CHECKING

from gofra.codegen.backends.amd64.frame import (
    build_local_variables_frame_offsets,
    preserve_calee_frame,
    restore_calee_frame,
)
from gofra.hir.operator import OperatorType
from gofra.types.primitive.void import VoidType

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from gofra.hir.variable import Variable
    from gofra.types._base import Type

    from ._context import AMD64CodegenContext
    from .registers import AMD64_GP_REGISTERS


def drop_cells_from_stack(context: AMD64CodegenContext, *, cells_count: int) -> None:
    """Drop stack cells from stack.

    Stack alignment should be review, but `popq` unlike `pop` will shift by 64 bits
    """
    assert cells_count > 0, "Tried to drop negative cells count from stack"
    for _ in range(cells_count):
        context.write("popq %rax")  # Use zero register?


def pop_cells_from_stack_into_registers(
    context: AMD64CodegenContext,
    *registers: AMD64_GP_REGISTERS,
) -> None:
    """Pop cells from stack and store into given registers.

    Stack alignment should be review, but probably this codegen ensure with `popq`/`pushq` that all cells are 64 bits
    """
    assert registers, "Expected registers to store popped result into!"

    for register in registers:
        context.write(f"popq %{register}")


def push_register_onto_stack(
    context: AMD64CodegenContext,
    register: AMD64_GP_REGISTERS,
) -> None:
    """Store given register onto stack under current stack pointer."""
    context.write(f"pushq %{register}")


def store_integer_into_register(
    context: AMD64CodegenContext,
    register: AMD64_GP_REGISTERS,
    value: int,
) -> None:
    """Store given value into given register (as QWORD)."""
    context.write(f"movq ${value}, %{register}")


def push_integer_onto_stack(
    context: AMD64CodegenContext,
    value: int,
) -> None:
    """Push given integer onto stack.

    Negative numbers is disallowed.

    TODO(@kirillzhosul, @stepanzubkov): Negative numbers IS disallowed
    TODO(@kirillzhosul, @stepanzubkov): Review max and etc like in AARCH64_MacOS
    """
    assert value >= 0, "Tried to push negative integer onto stack!"

    if value.bit_count() > 8 * 8:
        msg = "Can push only integers within 64 bits range (8 bytes, x64)"
        raise ValueError(msg)

    store_integer_into_register(context, register="rax", value=value)
    push_register_onto_stack(context, register="rax")


def push_static_address_onto_stack(
    context: AMD64CodegenContext,
    segment: str,
) -> None:
    """Push executable static memory address onto stack with page dereference."""
    context.write(f"leaq {segment}(%rip), %rax")
    push_register_onto_stack(context, register="rax")


def initialize_static_data_section(
    context: AMD64CodegenContext,
    static_strings: Mapping[str, str],
    static_variables: Mapping[str, Variable],
) -> None:
    """Initialize data section fields with given values.

    Section is an tuple (label, data)
    Data is an string (raw ASCII) or number (zeroed memory blob)
    TODO(@kirillzhosul, @stepanzubkov): Review alignment for data sections.
    """
    if static_strings:
        context.fd.write(".section .rodata\n")
        for name, data in static_strings.items():
            context.write(f'{name}: .asciz "{data}"')

    bss_variables = {
        k: v for k, v in static_variables.items() if v.initial_value is None
    }
    data_variables = {
        k: v for k, v in static_variables.items() if v.initial_value is not None
    }

    if bss_variables:
        context.fd.write(".section .bss\n")
        for name, variable in bss_variables.items():
            type_size = variable.size_in_bytes
            if type_size == 0:
                continue
            assert variable.initial_value is None
            context.write(f"{name}: .space {type_size}")

    if data_variables:
        context.fd.write(".section .data\n")
        for name, variable in data_variables.items():
            type_size = variable.size_in_bytes
            if type_size == 0:
                continue
            assert variable.initial_value is not None
            assert isinstance(variable.initial_value, int), (
                "Array initializer is not implemented on AMD64"
            )

            if type_size == 1:
                context.write(f"{name}: .byte {variable.initial_value}")
            elif type_size == 2:
                context.write(f"{name}: .value {variable.initial_value}")
            elif type_size <= 4:
                context.write(f"{name}: .long {variable.initial_value}")
            elif type_size <= 8:
                context.write(f"{name}: .quad {variable.initial_value}")
            else:
                msg = (
                    "Codegen does not supports initial values that out of 8 bytes range"
                )
                raise ValueError(msg)


def ipc_syscall_linux(
    context: AMD64CodegenContext,
    *,
    arguments_count: int,
    store_retval_onto_stack: bool,
    injected_args: list[int | None] | None,
) -> None:
    """Call system (syscall) and apply IPC ABI convention to arguments."""
    assert not injected_args or len(injected_args) == arguments_count + 1
    assert context.target.operating_system != "Windows", (
        "Windows Syscall usage is discouraged"
    )

    if not injected_args:
        injected_args = [None for _ in range(arguments_count + 1)]

    abi = context.abi
    registers_to_load = (
        abi.syscall_number_register,
        *abi.syscall_arguments_registers[:arguments_count][::-1],
    )

    for injected_argument, register in zip(
        injected_args,
        registers_to_load,
        strict=False,
    ):
        if injected_argument is not None:
            # Register injected and inferred from stack
            store_integer_into_register(
                context,
                register=register,
                value=injected_argument,
            )
            continue
        pop_cells_from_stack_into_registers(context, register)

    context.write("syscall")

    if store_retval_onto_stack:
        # Mostly related to optimizations above if we dont want to store result
        push_register_onto_stack(context, abi.retval_primitive_64bit_register)


def push_local_variable_address_from_frame_offset(
    context: AMD64CodegenContext,
    local_variables: Mapping[str, Variable],
    local_variable: str,
) -> None:
    current_offset = build_local_variables_frame_offsets(
        local_variables,
    ).offsets[local_variable]

    context.write(
        "movq %rbp, %rax",
        f"subq ${current_offset}, %rax",
    )
    push_register_onto_stack(context, register="rax")


def function_end_with_epilogue(
    context: AMD64CodegenContext,
    *,
    has_preserved_frame: bool,
    execution_trap_instead_return: bool = False,
    return_type: Type,
) -> None:
    """Functions epilogue at the end. Restores required fields (like stack-pointer)."""
    abi = context.abi
    if not isinstance(return_type, VoidType):
        if return_type.size_in_bytes > 16:
            msg = "Tried to return value which size in bytes requires indirect return register, NIP!"
            raise ValueError(msg)
        pop_cells_from_stack_into_registers(
            context,
            abi.retval_primitive_64bit_register,
        )

    if has_preserved_frame:
        restore_calee_frame(context)

    if execution_trap_instead_return:
        context.write("int3")
    else:
        context.write("retq")


def function_begin_with_prologue(  # noqa: PLR0913
    context: AMD64CodegenContext,
    *,
    function_name: str,
    as_global_linker_symbol: bool,
    preserve_frame: bool,
    arguments_count: int,
    local_variables: Mapping[str, Variable],
) -> None:
    """Begin an function symbol with prologue with preparing required (like stack-pointer).

    TODO(@kirillzhosul, @stepanzubkov): Review alignment for executable sections.
    """
    offsets = build_local_variables_frame_offsets(local_variables)
    if as_global_linker_symbol:
        context.fd.write(f".global {function_name}\n")

    context.fd.write(f"{function_name}:\n")

    if preserve_frame:
        preserve_calee_frame(context, offsets.local_space_size)

    if arguments_count:
        registers = context.abi.arguments_64bit_registers[:arguments_count]
        for register in registers:
            push_register_onto_stack(context, register)

    for variable in local_variables.values():
        initial_value = variable.initial_value
        if initial_value is None:
            continue
        assert isinstance(variable.initial_value, int), (
            "Array initializer is not implemented on AMD64"
        )

        current_offset = offsets.offsets[variable.name]
        context.write(f"movq ${initial_value}, %rax")
        context.write(f"mov %rax, {current_offset}(%rbp)")


def function_call(
    context: AMD64CodegenContext,
    *,
    name: str,
    type_contract_in: Sequence[Type],
    type_contract_out: Type,
) -> None:
    """Call an function using C ABI (Gofra native and C-FFI both functions).

    As Gofra under the hood uses C call convention for functions, this simplifies differences between C and Gofra calls.
    """
    i64_arguments_count = len(type_contract_in)
    store_return_value = not isinstance(type_contract_out, VoidType)

    argument_registers = context.abi.arguments_64bit_registers[:i64_arguments_count][
        ::-1
    ]
    if i64_arguments_count > len(argument_registers):
        msg = (
            f"C-FFI function call with {i64_arguments_count} arguments not supported. "
            f"Maximum {len(argument_registers)} register arguments supported. "
            "Stack argument passing not implemented."
        )
        raise NotImplementedError(msg)

    if i64_arguments_count < 0:
        msg = f"Tried to call function `{name}` with negative arguments count"
        raise ValueError(msg)

    if i64_arguments_count:
        pop_cells_from_stack_into_registers(context, *argument_registers)

    context.write(f"callq {name}")

    if store_return_value:
        push_register_onto_stack(context, context.abi.retval_primitive_64bit_register)


def store_into_memory_from_stack_arguments(context: AMD64CodegenContext) -> None:
    """Store value from into memory pointer, pointer and value acquired from stack."""
    pop_cells_from_stack_into_registers(context, "rax", "rbx")
    context.write("movq %rax, (%rbx)")


def load_memory_from_stack_arguments(context: AMD64CodegenContext) -> None:
    """Load memory as value using arguments from stack."""
    pop_cells_from_stack_into_registers(context, "rax")
    context.write("movq (%rax), %rax")
    push_register_onto_stack(context, "rax")


def perform_operation_onto_stack(
    context: AMD64CodegenContext,
    operation: OperatorType,
) -> None:
    """Perform *math* operation onto stack (pop arguments and push back result)."""
    registers = ("rax", "rbx")
    pop_cells_from_stack_into_registers(context, *registers)
    # TODO(@kirillzhosul): Optimize inc / dec (++, --) when incrementing / decrementing by known values

    match operation:
        case OperatorType.ARITHMETIC_PLUS:
            context.write("addq %rbx, %rax")

        case OperatorType.ARITHMETIC_MINUS:
            context.write("subq %rax, %rbx")

        case OperatorType.ARITHMETIC_MULTIPLY:
            context.write("mulq %rbx")

        case OperatorType.ARITHMETIC_DIVIDE:
            context.write(
                "movq $0, %rdx",
                "idivq %rbx",
            )
        case OperatorType.ARITHMETIC_MODULUS:
            context.write(
                "movq $0, %rdx",
                "idivq %rbx",
                "movq %rdx, %rax",
            )
        case OperatorType.BITWISE_XOR:
            context.write("xorq %rbx, %rax")
        case OperatorType.LOGICAL_OR | OperatorType.BITWISE_OR:
            context.write("orq %rbx, %rax")
        case OperatorType.SHIFT_RIGHT:
            context.write(
                "movq %rax, %rcx",
                "shrq %cl, %rbx",
                "movq %rbx, %rax",
            )
        case OperatorType.SHIFT_LEFT:
            context.write(
                "movq %rax, %rcx",
                "shlq %cl, %rbx",
                "movq %rbx, %rax",
            )
        case OperatorType.BITWISE_AND | OperatorType.LOGICAL_AND:
            context.write("andq %rbx, %rax")
        case (
            OperatorType.COMPARE_EQUALS
            | OperatorType.COMPARE_GREATER
            | OperatorType.COMPARE_GREATER_EQUALS
            | OperatorType.COMPARE_LESS
            | OperatorType.COMPARE_NOT_EQUALS
            | OperatorType.COMPARE_LESS_EQUALS
        ):
            logic_op = {
                OperatorType.COMPARE_NOT_EQUALS: "ne",
                OperatorType.COMPARE_GREATER_EQUALS: "ge",
                OperatorType.COMPARE_LESS_EQUALS: "le",
                OperatorType.COMPARE_LESS: "l",
                OperatorType.COMPARE_GREATER: "g",
                OperatorType.COMPARE_EQUALS: "e",
            }
            context.write(
                "cmpq %rax, %rbx",
                f"set{logic_op[operation]}b %al",
                "movzx %al, %rax",
            )
        case _:
            msg = f"{operation} cannot be performed by codegen `{perform_operation_onto_stack.__name__}`"
            raise ValueError(msg)
    push_register_onto_stack(context, "rax")


def evaluate_conditional_block_on_stack_with_jump(
    context: AMD64CodegenContext,
    jump_over_label: str,
) -> None:
    """Evaluate conditional block by popping current value under SP against zero.

    If condition is false (value on stack) then jump out that conditional block to `jump_over_label`
    """
    pop_cells_from_stack_into_registers(context, "rax")
    context.write(
        "cmpq $0, %rax",
        f"je {jump_over_label}",
    )
