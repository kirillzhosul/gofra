"""Assembly abstraction layer that hides declarative assembly OPs into functions that generates that for you."""

from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from .registers import (
    AARCH64_DOUBLE_WORD_BITS,
    AARCH64_GP_REGISTERS,
    AARCH64_HALF_WORD_BITS,
    AARCH64_STACK_ALIGNMENT,
    AARCH64_STACK_ALINMENT_BIN,
    FRAME_POINTER,
    LINK_REGISTER,
    STACK_POINTER,
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

    abi = context.abi
    registers_to_load = (
        abi.syscall_number_register,
        *abi.argument_registers[:arguments_count][::-1],
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
        push_register_onto_stack(context, abi.return_value_register)


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
    """Store value into memory pointer, pointer and value acquired from stack."""
    pop_cells_from_stack_into_registers(context, "X0", "X1")
    context.write("str X0, [X1]")


def call_cffi_function(
    context: AARCH64CodegenContext,
    *,
    name: str,
    arguments_count: int,
    push_return_value_onto_stack: bool,
) -> None:
    """Call an function with C-FFI ABI.

    C-FFI functions are different from internal (Gofra) ones.
    """
    if arguments_count > len(context.abi.argument_registers):
        msg = (
            f"C-FFI function call with {arguments_count} arguments not supported. "
            f"Maximum {len(context.abi.argument_registers)} register arguments supported. "
            "Stack argument passing not implemented."
        )
        raise NotImplementedError(msg)

    if arguments_count < 0:
        msg = "Tried to call function with C-FFI ABI with negative arguments count"
        raise ValueError(msg)

    abi = context.abi
    if arguments_count:
        registers = abi.argument_registers[:arguments_count][::-1]
        pop_cells_from_stack_into_registers(context, *registers)

    context.write(f"bl {name}")

    if push_return_value_onto_stack:
        push_register_onto_stack(context, abi.return_value_register)


def call_internal_function(context: AARCH64CodegenContext, *, name: str) -> None:
    """Call an function internally (e.g Gofra internal function without invokation of C-FFI ABI."""
    context.write(f"bl {name}")


def function_begin_with_prologue(
    context: AARCH64CodegenContext,
    *,
    name: str,
    global_name: str | None = None,
    preserve_frame: bool = True,
) -> None:
    """Begin an function symbol.

    Injects prologue with preparing required state (e.g registers, frame/stack pointers)

    :is_global_symbol: Mark that function symbol as global for linker
    :preserve_frame: If true will preserve function state for proper stack management and return adress
    """
    if global_name:
        context.fd.write(f".global {global_name}\n")

    context.fd.write(f".align {AARCH64_STACK_ALINMENT_BIN}\n")
    context.fd.write(f"{name}:\n")

    if preserve_frame:
        # Save frame pointer and link register
        context.write(f"stp {FRAME_POINTER}, {LINK_REGISTER}, [sp, #-16]!")
        context.write(f"mov {FRAME_POINTER}, sp")


def function_end_with_epilogue(
    context: AARCH64CodegenContext,
    *,
    has_preserved_frame: bool = True,
    execution_trap_instead_return: bool = False,
) -> None:
    """End function with proper epilogue.

    Epilogue is required to proper restore required state (e.g registers, frame/stack pointers)
    and possibly cleanup.

    :has_preserved_frame: If true, will restore that to jump out and proper stack management
    :execution_trap_instead_return: Internal, if true, will replace simple return with execution guard trap to raise from execution
    """
    if has_preserved_frame:
        # Restore frame pointer and link register
        context.write(f"ldp {FRAME_POINTER}, {LINK_REGISTER}, [{STACK_POINTER}], #16")

    if execution_trap_instead_return:
        execution_guard_trap(context)
        return

    context.write("ret")


def debugger_breakpoint_trap(context: AARCH64CodegenContext, number: int) -> None:
    """Place an debugger breakpoint (e.g trace trap).

    Will halt execution to the debugger, useful for debugging purposes.
    Also due to being an trap (e.g execution will be catched) allows to trap some execution places.
    (e.g start entry exit failure)
    """
    if not (0 <= number <= AARCH64_HALF_WORD_BITS):
        msg = "Expected 16-bit immediate for breakpoint trap number!"
        raise ValueError(msg)
    context.write(f"brk #{number & AARCH64_HALF_WORD_BITS}")


def execution_guard_trap(context: AARCH64CodegenContext) -> None:
    """Place a trap to prevent execution after function return.

    Prevents fatal errors when execution falls through exit call into
    unbound memory.
    """
    debugger_breakpoint_trap(context, number=0)
