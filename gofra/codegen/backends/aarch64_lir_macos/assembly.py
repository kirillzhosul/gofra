"""Assembly abstraction layer that hides declarative assembly OPs into functions that generates that for you."""

from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from gofra.codegen.lir.static import (
    LIRStaticSegmentCString,
    LIRStaticSegmentGlobalVariable,
)
from gofra.types import Type

from .frame import (
    build_local_variables_frame_offsets,
    preserve_calee_frame,
    restore_calee_frame,
)
from .registers import (
    AARCH64_DOUBLE_WORD_BITS,
    AARCH64_GP_REGISTERS,
    AARCH64_HALF_WORD_BITS,
    AARCH64_STACK_ALIGNMENT,
    AARCH64_STACK_ALINMENT_BIN,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from gofra.codegen.backends.general import CODEGEN_GOFRA_ON_STACK_OPERATIONS
    from gofra.codegen.lir import LIRProgram

    from ._context import AARCH64CodegenContext


def drop_stack_slots(
    context: AARCH64CodegenContext,
    *,
    slots_count: int,
    slot_size: int = AARCH64_STACK_ALIGNMENT,
) -> None:
    """Drop stack slots by shifting stack pointer (SP) by N bytes.

    In ARM64 context, a 'stack slot' typically represents an aligned unit
    of memory that can hold primitive values, pointers, or parts of larger objects.
    """
    if slot_size <= 0:
        msg = "`slots_count` must be positive, cannot drop zero or less stack slots"
        raise ValueError(msg)

    shift_in_bits = slot_size * slots_count
    context.write(f"add SP, SP, #{shift_in_bits}")


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


def push_local_variable_address_from_frame_offset(
    context: AARCH64CodegenContext,
    local_variables: Mapping[str, Type],
    local_variable: str,
) -> None:
    # Calculate negative offset from X29
    current_offset = build_local_variables_frame_offsets(local_variables).offsets[
        local_variable
    ]

    context.write(
        "mov X0, X29",
        f"sub X0, X0, #{current_offset} // X0 = FP, X0 = &{local_variable} (offset -{current_offset})",
    )
    push_register_onto_stack(context, register="X0")


def initialize_static_data_section(
    context: AARCH64CodegenContext,
    lir: LIRProgram,
) -> None:
    """Initialize data section fields with given values.

    Section is an tuple (label, data)
    Data is an string (raw ASCII) or number (zeroed memory blob)
    """
    context.fd.write(".section __DATA,__data\n")
    context.fd.write(f".align {AARCH64_STACK_ALINMENT_BIN}\n")

    for name, data in lir.static_segment.items():
        match data:
            case LIRStaticSegmentCString():
                context.fd.write(f'{name}: .asciz "{data.text}"\n')
            case LIRStaticSegmentGlobalVariable():
                context.fd.write(f"{name}: .space {data.type.size_in_bytes}\n")
            case _:
                raise ValueError


def syscall_prepare_arguments(
    context: AARCH64CodegenContext,
    arguments_count: int,
) -> None:
    injected_args = None
    assert not injected_args or len(injected_args) == arguments_count + 1

    if not injected_args:
        injected_args = [None for _ in range(arguments_count + 1)]

    abi = context.abi
    registers_to_load = (
        abi.syscall_number_register,
        *abi.argument_registers[:arguments_count][::-1],
    )

    for injected_argument, register in zip(
        injected_args,
        registers_to_load,
        strict=False,
    ):
        if injected_argument is not None:
            # Register injected and infered from stack
            store_integer_into_register(
                context,
                register=register,
                value=injected_argument,
            )
            continue
        pop_cells_from_stack_into_registers(context, register)


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

    for injected_argument, register in zip(
        injected_args,
        registers_to_load,
        strict=False,
    ):
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

    context.write(f"// OP on-stack {operation}")
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
        case "||" | "|":
            # Use bitwise one here even for logical one as we have typechecker which expects boolean types.
            context.write("orr X0, X0, X1")
        case "&&" | "&":
            # Use bitwise one here even for logical one as we have typechecker which expects boolean types.
            context.write("and X0, X0, X1")
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


def function_save_frame(
    context: AARCH64CodegenContext,
    *,
    local_vars: Mapping[str, Type],
) -> None:
    local_offsets = build_local_variables_frame_offsets(local_vars)

    preserve_calee_frame(context, local_space_size=local_offsets.local_space_size)


def function_restore_frame(context: AARCH64CodegenContext) -> None:
    restore_calee_frame(context)


def function_acquire_arguments(
    context: AARCH64CodegenContext,
    arguments: Sequence[Type],
) -> None:
    abi = context.abi
    if len(arguments):
        registers = abi.argument_registers[: len(arguments)]
        for register in registers:
            push_register_onto_stack(context, register)


def function_prepare_retval(
    context: AARCH64CodegenContext,
) -> None:
    abi = context.abi
    pop_cells_from_stack_into_registers(context, abi.return_value_register)


def function_return(context: AARCH64CodegenContext) -> None:
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


def function_call_prepare_arguments(
    context: AARCH64CodegenContext,
    arguments: Sequence[Type],
) -> None:
    """Call an function using C ABI (Gofra native and C-FFI both functions).

    As Gofra under the hood uses C call convention for functions, this simplifies differences between C and Gofra calls.

    Uses Branch-With-Link (BL) instruction to `jump` into an function and passing Link-Register (LR, x30 on AARCH64) to callee
    Passes arguments before function call with C call convention (e.g via registers and stack depending on arguments byte size and type),
    Restores single return value if requested from retval register.

    Most of the call logic is covered into function own prologue, which unpacks arguments and stores calee stack frame
    """
    abi = context.abi
    if len(arguments) > len(abi.argument_registers):
        msg = (
            f"C-FFI function call with {len(arguments)} arguments not supported. "
            f"Maximum {len(context.abi.argument_registers)} register arguments supported. "
            "Stack argument passing not implemented."
        )
        raise NotImplementedError(msg)

    if len(arguments) < 0:
        msg = "Tried to call function with negative arguments count"
        raise ValueError(msg)

    if len(arguments):
        registers = abi.argument_registers[: len(arguments)][::-1]
        pop_cells_from_stack_into_registers(context, *registers)
