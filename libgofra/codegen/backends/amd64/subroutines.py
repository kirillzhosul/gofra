"""Assembly abstraction layer that hides declarative assembly OPs into functions that generates that for you."""

from __future__ import annotations

from typing import TYPE_CHECKING

from libgofra.codegen.backends.amd64.frame import (
    preserve_calee_frame,
    restore_calee_frame,
)
from libgofra.codegen.backends.frame import build_local_variables_frame_offsets
from libgofra.types.primitive.void import VoidType

from .assembly import pop_cells_from_stack_into_registers, push_register_onto_stack
from .stack_local_initializer import (
    write_function_local_stack_variables_initializer,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from libgofra.codegen.backends.amd64._context import AMD64CodegenContext
    from libgofra.hir.variable import Variable
    from libgofra.types._base import Type


def function_begin_with_prologue(  # noqa: PLR0913
    context: AMD64CodegenContext,
    *,
    function_name: str,
    as_global_linker_symbol: bool,
    preserve_frame: bool,
    arguments_count: int,
    local_variables: Mapping[str, Variable[Type]],
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

    write_function_local_stack_variables_initializer(
        context,
        local_variables=local_variables,
    )


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
