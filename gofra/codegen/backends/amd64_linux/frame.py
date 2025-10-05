from collections.abc import Mapping
from typing import NamedTuple

from gofra.codegen.backends.alignment import align_to_highest_size
from gofra.parser.variables import Variable

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
    And we need convient mapping for accessing local variables allocated at that space.

    That function constucts something like:
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
        current_offset += var.type.size_in_bytes

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
