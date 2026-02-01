from libgofra.codegen.backends.alignment import align_to_highest_size
from libgofra.codegen.backends.amd64._context import AMD64CodegenContext

# Size of frame head (RBP register)
FRAME_HEAD_SIZE = 8


def preserve_callee_frame(
    context: AMD64CodegenContext,
    local_space_size: int,
) -> None:
    context.write("pushq %rbp")
    context.write("movq %rsp, %rbp")

    if local_space_size > 0:
        aligned_size = align_to_highest_size(local_space_size)
        context.write(f"subq ${aligned_size}, %rsp")


def restore_callee_frame(
    context: AMD64CodegenContext,
) -> None:
    """Restore preserved by callee frame.

    Read more in: `preserve_callee_frame`
    """
    context.write("movq %rbp, %rsp")
    context.write("popq %rbp")
