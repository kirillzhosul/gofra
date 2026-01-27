"""Assembly abstraction layer that hides declarative assembly OPs into functions that generates that for you."""

from __future__ import annotations

from typing import TYPE_CHECKING

from libgofra.codegen.backends.aarch64.abi_call_convention import (
    load_return_value_from_stack_into_abi_registers,
)
from libgofra.codegen.backends.aarch64.frame import (
    preserve_calee_frame,
    restore_calee_frame,
)
from libgofra.codegen.backends.aarch64.registers import AARCH64_STACK_ALIGNMENT_BIN
from libgofra.codegen.backends.frame import build_local_variables_frame_offsets

from .primitive_instructions import (
    push_register_onto_stack,
)
from .stack_local_initializer import (
    write_function_local_stack_variables_initializer,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from libgofra.codegen.backends.aarch64._context import AARCH64CodegenContext
    from libgofra.hir.variable import Variable
    from libgofra.types._base import Type

DEFAULT_FUNCTIONS_ALIGNMENT = AARCH64_STACK_ALIGNMENT_BIN


def function_begin_with_prologue(  # noqa: PLR0913
    context: AARCH64CodegenContext,
    *,
    name: str,
    global_name: str | None = None,
    preserve_frame: bool = True,
    local_variables: Mapping[str, Variable[Type]],
    parameters: Sequence[Type],
) -> None:
    """Begin an function symbol.

    Injects prologue with preparing required state (e.g registers, frame/stack pointers)

    :is_global_symbol: Mark that function symbol as global for linker
    :preserve_frame: If true will preserve function state for proper stack management and return address
    """
    if global_name:
        context.fd.write(f".globl {global_name}\n")

    alignment = (
        DEFAULT_FUNCTIONS_ALIGNMENT
        if context.config.align_functions_bytes is None
        else context.config.align_functions_bytes
    )
    if alignment > 1:
        if alignment % 2 == 0:
            context.fd.write(f".p2align {alignment // 2}\n")
        else:
            context.fd.write(f".align {alignment}\n")

    context.fd.write(f"{name}:\n")
    if context.config.dwarf_emit_cfi:
        context.fd.write(".cfi_startproc\n")

    if preserve_frame:
        local_offsets = build_local_variables_frame_offsets(local_variables)
        preserve_calee_frame(context, local_space_size=local_offsets.local_space_size)

    if parameters:
        registers = context.abi.arguments_64bit_registers[: len(parameters)]
        for register in registers:
            push_register_onto_stack(context, register)

    write_function_local_stack_variables_initializer(
        context,
        local_variables=local_variables,
    )


def function_return(
    context: AARCH64CodegenContext,
    *,
    has_preserved_frame: bool = True,
    return_type: Type,
) -> None:
    """Return from an function.

    Emits proper epilogue to restore required state

    :has_preserved_frame: If true, will restore that to jump out and proper stack management
    """
    load_return_value_from_stack_into_abi_registers(context, t=return_type)

    if has_preserved_frame:
        restore_calee_frame(context)

    context.write("ret")


def function_end_with_epilogue(
    context: AARCH64CodegenContext,
    *,
    has_preserved_frame: bool,
    return_type: Type,
    is_early_return: bool,
) -> None:
    """End function with proper epilogue.

    Epilogue is required to proper restore required state (e.g registers, frame/stack pointers)
    and possibly cleanup.

    :has_preserved_frame: If true, will restore that to jump out and proper stack management
    :is_early_return: If true, will not emit end end of procedure symbol (e.g directly early return, not finish)
    """
    function_return(
        context,
        has_preserved_frame=has_preserved_frame,
        return_type=return_type,
    )
    if not is_early_return and context.config.dwarf_emit_cfi:
        context.fd.write(".cfi_endproc\n")
