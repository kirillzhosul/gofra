from collections.abc import Mapping

from libgofra.codegen.backends.aarch64._context import AARCH64CodegenContext
from libgofra.codegen.backends.aarch64.primitive_instructions import (
    push_register_onto_stack,
)
from libgofra.codegen.backends.frame import build_local_variables_frame_offsets
from libgofra.hir.variable import Variable
from libgofra.types._base import Type

# Size of frame head (FP, LR registers)
FRAME_HEAD_SIZE = 8 * 2

STORE_PAIR_MAX_RANGE = 8 * 64 - 8


def preserve_calee_frame(
    context: AARCH64CodegenContext,
    local_space_size: int,
) -> None:
    """Save callee LR and FP registers on stack as frame head.

    Preserving FP (frame-pointer) is required for restoring SP to initial pointer (as may modified in other functions) when function ends so others can override that garbage in *memory*
    Preserving LR (link-register) is required for jumping into another functions via branch-with-link (BL) as that will overwrite LR with new value, but in that case we can restore that.
    """
    assert FRAME_HEAD_SIZE % 16 == 0, (
        f"Frame head must be aligned by 16 bytes, got {FRAME_HEAD_SIZE}"
    )

    frame_size = FRAME_HEAD_SIZE + local_space_size
    assert frame_size % 16 == 0, (
        f"Frame in total must be aligned by 16 bytes, got {frame_size}"
    )

    assert local_space_size < STORE_PAIR_MAX_RANGE, (
        f"Cannot locate current local frame without relocation, auto relocation is not implemented [lsp: {local_space_size}]"
    )
    if context.config.dwarf_emit_cfi:
        context.write(".cfi_def_cfa sp, 0")
    context.write(f"sub SP, SP, #{frame_size}")
    if context.config.dwarf_emit_cfi:
        context.write(f".cfi_def_cfa_offset {frame_size}")
    context.write(f"stp X29, X30, [SP, #{local_space_size}]")

    fp_offset = frame_size - local_space_size
    lr_offset = frame_size - local_space_size - 8
    if context.config.dwarf_emit_cfi:
        context.write(f".cfi_offset x29, -{fp_offset}")
        context.write(f".cfi_offset x30, -{lr_offset}")

    context.write(f"add X29, SP, #{local_space_size}")
    if context.config.dwarf_emit_cfi:
        context.write(".cfi_def_cfa_register x29")


def restore_calee_frame(context: AARCH64CodegenContext) -> None:
    """Restore preserved by callee frame.

    Read more in: `preserve_callee_frame`
    """
    assert FRAME_HEAD_SIZE % 16 == 0, "Frame head must be aligned by 16 bytes"
    context.write("mov SP, X29")
    context.write(f"ldp X29, X30, [SP], #{FRAME_HEAD_SIZE}")


def push_local_variable_address_from_frame_offset(
    context: AARCH64CodegenContext,
    local_variables: Mapping[str, Variable[Type]],
    local_variable: str,
) -> None:
    # Calculate negative offset from X29
    current_offset = build_local_variables_frame_offsets(local_variables).offsets[
        local_variable
    ]

    context.write(
        "mov X0, X29",
        f"sub X0, X0, #{current_offset}",
    )
    push_register_onto_stack(context, register="X0")
