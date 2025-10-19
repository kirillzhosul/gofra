from collections.abc import Mapping
from typing import NamedTuple

from gofra.codegen.backends.alignment import align_to_highest_size
from gofra.codegen.backends.amd64._context import AMD64CodegenContext
from gofra.hir.variable import Variable

# Size of frame head (RBP register)
FRAME_HEAD_SIZE = 8


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

    return LocalVariablesFrameOffsets(
        offsets=offsets,
        local_space_size=local_space_size,
    )


def preserve_calee_frame(
    context: AMD64CodegenContext,
    local_space_size: int,
) -> None:
    context.write("pushq %rbp")
    context.write("movq %rsp, %rbp")

    if local_space_size > 0:
        aligned_size = align_to_highest_size(local_space_size)
        context.write(f"subq ${aligned_size}, %rsp")


def restore_calee_frame(
    context: AMD64CodegenContext,
) -> None:
    """Restore preserved by callee frame.

    Read more in: `preserve_callee_frame`
    """
    context.write("movq %rbp, %rsp")
    context.write("popq %rbp")
