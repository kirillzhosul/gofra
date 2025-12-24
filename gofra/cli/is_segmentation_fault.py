from signal import SIGSEGV


def is_segmentation_fault(exit_code: int) -> bool:
    """Check is given exit code is an standard segmentation fault."""
    return exit_code in (
        SIGSEGV,  # Direct
        -SIGSEGV,  # Mostly linux
        128 + SIGSEGV,  # Overflow (must be Linux also)
    )
