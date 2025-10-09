from collections.abc import Mapping
from typing import NamedTuple

from gofra.codegen.backends.aarch64_macos._context import (
    AARCH64CodegenContext,
)
from gofra.codegen.backends.alignment import align_to_highest_size
from gofra.hir.variable import Variable

# Size of frame head (FP, LR registers)
FRAME_HEAD_SIZE = 8 * 2

STORE_PAIR_MAX_RANGE = 8 * 64 - 8


class LocalVariablesFrameOffsets(NamedTuple):
    """Offsets within frame for local variables."""

    offsets: Mapping[str, int]
    local_space_size: int


def build_local_variables_frame_offsets(
    variables: Mapping[str, Variable],
) -> LocalVariablesFrameOffsets:
    """Construct mapping from local variable name to stack frame offset where that variable should live.

    We allocate some space under stack/frame pointer for local variables (beside FP and LR itself).
    And we need convenient mapping for accessing local variables allocated at that space.

    That function constructs something like:
    {
        'var1': 8, # +8 bytes from frame
        'var2': 16 # +16 bytes from frame
        ...
    }

    Total offsets must be aligned to 16 bytes on AARCH64, so sum of these variables is not 24, but 32 bytes (space may be used or leftover for alignment)

    So looking at the frame with alignment:
    [SP]
    [SP - 8]:  FP
    [SP - 16]: LR
    """
    offsets: dict[str, int] = {}
    current_offset = 8

    for var_name, var in variables.items():
        offsets[var_name] = current_offset
        current_offset += var.size_in_bytes

    # Alignment is required on AARCH64
    local_space_size = align_to_highest_size(current_offset)

    if local_space_size > STORE_PAIR_MAX_RANGE:  # [-512, 504] STP limitations
        # TODO(@kirillzhosul): Add proper auto relocation / fix STP limitations
        msg = f"Cannot locate current local variables on a frame or relocate them, please locate big local variables in global space! Max local frame size: {STORE_PAIR_MAX_RANGE}, but currently it is: {local_space_size} bytes (aligned)!"
        raise NotImplementedError(msg)

    return LocalVariablesFrameOffsets(
        offsets=offsets,
        local_space_size=local_space_size,
    )


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
    context.comment(f"; Preserve frame ({FRAME_HEAD_SIZE}b + {local_space_size}b)")
    context.write(f"sub SP, SP, #{frame_size}")
    context.write(f"stp X29, X30, [SP, #{local_space_size}]")
    context.write(f"add X29, SP, #{local_space_size}")


def restore_calee_frame(context: AARCH64CodegenContext) -> None:
    """Restore preserved by callee frame.

    Read more in: `preserve_callee_frame`
    """
    assert FRAME_HEAD_SIZE % 16 == 0, "Frame head must be aligned by 16 bytes"
    context.comment("; Restore frame (LR, FP, SP)")
    context.write("mov SP, X29")
    context.write(f"ldp X29, X30, [SP], #{FRAME_HEAD_SIZE}")
