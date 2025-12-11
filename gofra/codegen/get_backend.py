from gofra.targets import Target

from .backends import (
    CodeGeneratorBackend,
    generate_aarch64_macos_backend,
    generate_amd64_backend,
)
from .exceptions import CodegenUnsupportedBackendTargetPairError


def get_backend_for_target(
    target: Target,
) -> CodeGeneratorBackend:
    """Get code generator backend for specified ARCHxOS pair."""
    match target.triplet:
        case "arm64-apple-darwin":
            return generate_aarch64_macos_backend
        case "amd64-unknown-linux" | "amd64-unknown-windows":
            return generate_amd64_backend
        case _:
            raise CodegenUnsupportedBackendTargetPairError(target=target)
