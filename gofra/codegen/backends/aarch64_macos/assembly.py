"""Assembly abstraction layer that hides declarative assembly OPs into functions that generates that for you."""

from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from .registers import (
    AARCH64_DOUBLE_WORD_BITS,
    AARCH64_GP_REGISTERS,
    AARCH64_HALF_WORD_BITS,
    AARCH64_MACOS_ABI_ARGUMENT_REGISTERS,
    AARCH64_MACOS_ABI_RETVAL_REGISTER,
    AARCH64_MACOS_SYSCALL_NUMBER_REGISTER,
    AARCH64_STACK_ALIGNMENT,
    AARCH64_STACK_ALINMENT_BIN,
)

if TYPE_CHECKING:
    from gofra.codegen.backends.aarch64_macos._context import AARCH64CodegenContext
    from gofra.codegen.backends.general import CODEGEN_GOFRA_ON_STACK_OPERATIONS


def drop_cells_from_stack(context: AARCH64CodegenContext, *, cells_count: int) -> None:
    """Drop stack cells from stack by shifting stack pointer (SP) by N bytes.

    Stack must be aligned so we use `AARCH64_STACK_ALIGNMENT`
    """
    assert cells_count > 0, "Tried to drop negative cells count from stack"
    stack_pointer_shift = AARCH64_STACK_ALIGNMENT * cells_count
    context.write(f"add SP, SP, #{stack_pointer_shift}")


def pop_cells_from_stack_into_registers(
    context: AARCH64CodegenContext,
    *registers: AARCH64_GP_REGISTERS,
) -> None:
    """Pop cells from stack and store into given registers.

    Each cell is 8 bytes, but stack pointer is always adjusted by `AARCH64_STACK_ALIGNMENT` bytes
    to preserve stack alignment.
    """
    assert registers, "Expected registers to store popped result into!"

    for register in registers:
        context.write(
            f"ldr {register}, [SP]",
            f"add SP, SP, #{AARCH64_STACK_ALIGNMENT}",
        )


def push_register_onto_stack(
    context: AARCH64CodegenContext,
    register: AARCH64_GP_REGISTERS,
) -> None:
    """Store given register onto stack under current stack pointer."""
    context.write(f"str {register}, [SP, -{AARCH64_STACK_ALIGNMENT}]!")


def store_integer_into_register(
    context: AARCH64CodegenContext,
    register: AARCH64_GP_REGISTERS,
    value: int,
) -> None:
    """Store given value into given register."""
    context.write(f"mov {register}, #{value}")


def push_integer_onto_stack(
    context: AARCH64CodegenContext,
    value: int,
) -> None:
    """Push given integer onto stack with auto shifting less-significant bytes.

    Value must be less than 16 bytes (18_446_744_073_709_551_615).
    Negative numbers is dissalowed.

    TODO(@kirillzhosul): Negative numbers IS dissalowed:
        Consider using signed two complement representation with sign bit (highest bit) set
    """
    assert value >= 0, "Tried to push negative integer onto stack!"
    assert value <= AARCH64_DOUBLE_WORD_BITS, (
        "Tried to push integer that exceeding 16 bytes (64 bits register)."
    )

    if value <= AARCH64_HALF_WORD_BITS:
        # We have small immediate value which we may just store without shifts
        context.write(f"mov X0, #{value}")
        push_register_onto_stack(context, register="X0")
        return

    preserve_bits = False
    for shift in range(0, 64, 16):
        chunk = hex((value >> shift) & AARCH64_HALF_WORD_BITS)
        if chunk == "0x0":
            # Zeroed chunk so we dont push it as register is zerod
            continue

        if not preserve_bits:
            # Store upper bits
            context.write(f"movz X0, #{chunk}, lsl #{shift}")
            preserve_bits = True
            continue

        # Store lower bits
        context.write(f"movk X0, #{chunk}, lsl #{shift}")

    push_register_onto_stack(context, register="X0")


def push_static_address_onto_stack(
    context: AARCH64CodegenContext,
    segment: str,
) -> None:
    """Push executable static memory addresss onto stack with page dereference."""
    context.write(
        f"adrp X0, {segment}@PAGE",
        f"add X0, X0, {segment}@PAGEOFF",
    )
    push_register_onto_stack(context, register="X0")


def evaluate_conditional_block_on_stack_with_jump(
    context: AARCH64CodegenContext,
    jump_over_label: str,
) -> None:
    """Evaluate conditional block by popping current value under SP againts zero.

    If condition is false (value on stack) then jump out that conditional block to `jump_over_label`
    """
    pop_cells_from_stack_into_registers(context, "X0")
    context.write(
        "cmp X0, #0",
        f"beq {jump_over_label}",
    )


def initialize_static_data_section(
    context: AARCH64CodegenContext,
    static_data_section: list[tuple[str, str | int]],
) -> None:
    """Initialize data section fields with given values.

    Section is an tuple (label, data)
    Data is an string (raw ASCII) or number (zeroed memory blob)
    """
    context.fd.write(".section __DATA,__data\n")
    context.fd.write(f".align {AARCH64_STACK_ALINMENT_BIN}\n")

    for name, data in static_data_section:
        if isinstance(data, str):
            context.fd.write(f'{name}: .asciz "{data}"\n')
            continue
        context.fd.write(f"{name}: .space {data}\n")


def ipc_syscall_macos(
    context: AARCH64CodegenContext,
    *,
    arguments_count: int,
    store_retval_onto_stack: bool,
    injected_args: list[int | None] | None,
) -> None:
    """Call system (syscall) via supervisor call and apply IPC ABI convention to arguments."""
    assert not injected_args or len(injected_args) == arguments_count + 1

    if not injected_args:
        injected_args = [None for _ in range(arguments_count + 1)]

    registers_to_load = (
        AARCH64_MACOS_SYSCALL_NUMBER_REGISTER,
        *AARCH64_MACOS_ABI_ARGUMENT_REGISTERS[:arguments_count][::-1],
    )

    for injected_argument, register in zip(injected_args, registers_to_load):
        if injected_argument is not None:
            # Register injected and infered from stack
            store_integer_into_register(
                context,
                register=register,
                value=injected_argument,
            )
            continue
        pop_cells_from_stack_into_registers(context, register)

    # Supervisor call (syscall)
    context.write("svc #0")

    if store_retval_onto_stack:
        # Mostly related to optimizations above if we dont want to store result
        push_register_onto_stack(context, AARCH64_MACOS_ABI_RETVAL_REGISTER)


def perform_operation_onto_stack(
    context: AARCH64CodegenContext,
    operation: CODEGEN_GOFRA_ON_STACK_OPERATIONS,
) -> None:
    """Perform *math* operation onto stack (pop arguments and push back result)."""
    is_unary = operation in ("++", "--")
    registers = ("X0",) if is_unary else ("X0", "X1")
    pop_cells_from_stack_into_registers(context, *registers)

    match operation:
        case "+":
            context.write("add X0, X1, X0")
        case "-":
            context.write("sub X0, X1, X0")
        case "*":
            context.write("mul X0, X1, X0")
        case "//":
            context.write("sdiv X0, X1, X0")
        case "%":
            context.write(
                "udiv X2, X1, X0",
                "mul X2, X2, X0",
                "sub X0, X1, X2",
            )
        case "++":
            context.write("add X0, X0, #1")
        case "--":
            context.write("sub X0, X0, #1")
        case "!=" | ">=" | "<=" | "<" | ">" | "==":
            logic_op = {
                "!=": "ne",
                ">=": "ge",
                "<=": "le",
                "<": "lt",
                ">": "gt",
                "==": "eq",
            }
            context.write(
                "cmp X1, X0",
                f"cset X0, {logic_op[operation]}",
            )
        case _:
            assert_never()
    push_register_onto_stack(context, "X0")


def load_memory_from_stack_arguments(context: AARCH64CodegenContext) -> None:
    """Load memory as value using arguments from stack."""
    pop_cells_from_stack_into_registers(context, "X0")
    context.write("ldr X0, [X0]")
    push_register_onto_stack(context, "X0")


def store_into_memory_from_stack_arguments(context: AARCH64CodegenContext) -> None:
    """Store value from into memory pointer, pointer and value acquired from stack."""
    pop_cells_from_stack_into_registers(context, "X0", "X1")
    context.write("str X0, [X1]")


def call_function_block(
    context: AARCH64CodegenContext,
    function_name: str,
    *,
    abi_ffi_push_retval_onto_stack: bool,
    abi_ffi_arguments_count: int,
) -> None:
    """Call an function with preparing required fields (like stack-pointer).

    Also allows to call ABI/FFI function with providing arguments and return value (retval) via:
    `abi_ffi_push_retval_onto_stack` / `abi_ffi_arguments_count`
    """
    assert abi_ffi_arguments_count >= 0, "FFI arguments count cannot go negative"
    if abi_ffi_arguments_count:
        arguments = abi_ffi_arguments_count
        registers = AARCH64_MACOS_ABI_ARGUMENT_REGISTERS[:arguments][::-1]
        pop_cells_from_stack_into_registers(context, *registers)

    context.write(f"bl {function_name}")

    if abi_ffi_push_retval_onto_stack:
        push_register_onto_stack(context, AARCH64_MACOS_ABI_RETVAL_REGISTER)


def function_begin_with_prologue(
    context: AARCH64CodegenContext,
    *,
    function_name: str,
    as_global_linker_symbol: bool,
) -> None:
    """Begin an function symbol with prologue with preparing required (like stack-pointer)."""
    if as_global_linker_symbol:
        context.fd.write(f".global {function_name}\n")
    context.fd.write(f".align {AARCH64_STACK_ALINMENT_BIN}\n")
    context.fd.write(f"{function_name}:\n")


def function_end_with_epilogue(context: AARCH64CodegenContext) -> None:
    """Functions epilogue at the end. Restores required fields (like stack-pointer)."""
    context.write("ret")
