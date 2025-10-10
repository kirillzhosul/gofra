"""Assembly abstraction layer that hides declarative assembly OPs into functions that generates that for you."""

from __future__ import annotations

from typing import TYPE_CHECKING

from gofra.codegen.backends.aarch64_macos.assembly import (
    pop_cells_from_stack_into_registers,
    push_register_onto_stack,
    store_integer_into_register,
)
from gofra.codegen.lir.static import (
    LIRStaticSegmentCString,
    LIRStaticSegmentGlobalVariable,
)

from .frame import (
    build_local_variables_frame_offsets,
    preserve_calee_frame,
    restore_calee_frame,
)
from .registers import (
    AARCH64_HALF_WORD_BITS,
    AARCH64_STACK_ALIGNMENT_BIN,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from gofra.codegen.backends.aarch64_macos._context import AARCH64CodegenContext
    from gofra.codegen.lir import LIRProgram
    from gofra.types import Type


def initialize_static_data_section(
    context: AARCH64CodegenContext,
    lir: LIRProgram,
) -> None:
    """Initialize data section fields with given values.

    Section is an tuple (label, data)
    Data is an string (raw ASCII) or number (zeroed memory blob)
    """
    context.fd.write(".section __DATA,__data\n")
    context.fd.write(f".align {AARCH64_STACK_ALIGNMENT_BIN}\n")

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
            # Register injected and inferred from stack
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
            # Register injected and inferred from stack
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
    Also due to being an trap (e.g execution will be caught) allows to trap some execution places.
    (e.g start entry exit failure)
    """
    if not (0 <= number <= AARCH64_HALF_WORD_BITS):
        msg = "Expected 16-bit immediate for breakpoint trap number!"
        raise ValueError(msg)
    context.write(f"brk #{number & AARCH64_HALF_WORD_BITS}")


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
