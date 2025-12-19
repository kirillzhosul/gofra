"""Assembly abstraction layer that hides declarative assembly OPs into functions that generates that for you."""

from __future__ import annotations

from typing import TYPE_CHECKING

from libgofra.codegen.backends.aarch64.primitive_instructions import (
    pop_cells_from_stack_into_registers,
    push_register_onto_stack,
    store_integer_into_register,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from libgofra.codegen.backends.aarch64._context import AARCH64CodegenContext

AARCH64_MACOS_EPILOGUE_EXIT_CODE = 0
AARCH64_MACOS_EPILOGUE_EXIT_SYSCALL_NUMBER = 1


def ipc_aarch64_syscall(
    context: AARCH64CodegenContext,
    *,
    arguments_count: int,
    store_retval_onto_stack: bool,
    injected_args: Sequence[int | None] | None,
) -> None:
    """Call system (syscall) via supervisor call and apply IPC ABI convention to arguments."""
    assert not injected_args or len(injected_args) == arguments_count + 1

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

    # Supervisor call (syscall)
    # assume 0 - 65335 (16 bit)
    context.write("svc #0")

    # System calls always returns `long` type (e.g integer 64 bits (default one for Gofra))
    if store_retval_onto_stack:
        # TODO(@kirillzhosul): Research refactoring with using calling-convention system (e.g for system calls (syscall/cffi/fast-call convention))
        # TODO(@kirillzhosul): Research weirdness of kernel `errno`, not setting carry flag
        push_register_onto_stack(
            context,
            abi.retval_primitive_64bit_register,
        )
