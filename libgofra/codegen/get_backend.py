from typing import assert_never

from libgofra.targets import Target

from .backends import (
    AARCH64CodegenBackend,
    AMD64CodegenBackend,
    CodeGeneratorBackend,
)


def get_backend_for_target(
    target: Target,
) -> type[CodeGeneratorBackend]:
    """Get code generator backend for specified ARCHxOS pair."""
    match target.architecture:
        case "ARM64":
            return AARCH64CodegenBackend
        case "AMD64":
            return AMD64CodegenBackend
        case _:
            assert_never(target.architecture)
