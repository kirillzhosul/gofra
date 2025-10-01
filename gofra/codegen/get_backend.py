from gofra.feature_flags import FEATURE_USE_LIR_CODEGEN_IR
from gofra.targets import Target

from .backends import (
    CodeGeneratorBackend,
    generate_aarch64_lir_macos_backend,
    generate_aarch64_macos_backend,
    generate_amd64_linux_backend,
    generate_amd64_windows_backend,
)
from .exceptions import CodegenUnsupportedBackendTargetPairError


def get_backend_for_target(
    target: Target,
) -> CodeGeneratorBackend:
    """Get code generator backend for specified ARCHxOS pair."""
    match target.triplet:
        case "arm64-apple-darwin":
            if FEATURE_USE_LIR_CODEGEN_IR:
                return generate_aarch64_lir_macos_backend
            return generate_aarch64_macos_backend
        case "amd64-unknown-linux":
            assert not FEATURE_USE_LIR_CODEGEN_IR, (
                "FEATURE_USE_LIR_CODEGEN_IR is only avaiable on Darwin target"
            )
            return generate_amd64_linux_backend
        case "amd64-unknown-windows":
            assert not FEATURE_USE_LIR_CODEGEN_IR, (
                "FEATURE_USE_LIR_CODEGEN_IR is only avaiable on Darwin target"
            )

            return generate_amd64_windows_backend
        case _:
            raise CodegenUnsupportedBackendTargetPairError(target=target)
