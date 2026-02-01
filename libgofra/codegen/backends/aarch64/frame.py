from collections.abc import Mapping
from typing import TYPE_CHECKING

from libgofra.codegen.backends.aarch64.primitive_instructions import (
    push_register_onto_stack,
)
from libgofra.codegen.backends.frame import build_local_variables_frame_offsets
from libgofra.hir.variable import Variable
from libgofra.types._base import Type

if TYPE_CHECKING:
    from libgofra.codegen.backends.aarch64.codegen import AARCH64CodegenBackend

# Size of frame head (FP, LR registers)
FRAME_HEAD_SIZE = 8 * 2

STORE_PAIR_MAX_RANGE = 8 * 64 - 8


def preserve_callee_frame(
    context: "AARCH64CodegenBackend",
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
        context.directive("cfi_def_cfa", "sp", 0)
    context.instruction(f"sub SP, SP, #{frame_size}")
    if context.config.dwarf_emit_cfi:
        context.directive("cfi_def_cfa_offset", frame_size)
    context.instruction(f"stp X29, X30, [SP, #{local_space_size}]")

    fp_offset = frame_size - local_space_size
    lr_offset = frame_size - local_space_size - 8
    if context.config.dwarf_emit_cfi:
        context.directive("cfi_offset", "x29", -fp_offset)
        context.directive("cfi_offset", "x30", -lr_offset)

    context.instruction(f"add X29, SP, #{local_space_size}")
    if context.config.dwarf_emit_cfi:
        context.directive("cfi_def_cfa_register", "x29")


def restore_callee_frame(context: "AARCH64CodegenBackend") -> None:
    """Restore preserved by callee frame.

    Read more in: `preserve_callee_frame`
    """
    assert FRAME_HEAD_SIZE % 16 == 0, "Frame head must be aligned by 16 bytes"
    context.instruction("mov SP, X29")
    context.instruction(f"ldp X29, X30, [SP], #{FRAME_HEAD_SIZE}")


def push_local_variable_address_from_frame_offset(
    context: "AARCH64CodegenBackend",
    local_variables: Mapping[str, Variable[Type]],
    local_variable: str,
) -> None:
    # Calculate negative offset from X29
    current_offset = build_local_variables_frame_offsets(local_variables).offsets[
        local_variable
    ]

    context.instruction("mov X0, X29")
    context.instruction(f"sub X0, X0, #{current_offset}")
    push_register_onto_stack(context, register="X0")
