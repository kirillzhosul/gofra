from gofra.codegen.backends.aarch64_macos._context import AARCH64CodegenContext

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
