"""Code generation backend module.

Provides code generation backends (codegen) for emitting assembly from IR.
"""

from .aarch64_lir_macos import generate_aarch64_lir_macos_backend
from .aarch64_macos import generate_aarch64_macos_backend
from .amd64_linux import generate_amd64_linux_backend
from .amd64_windows import generate_amd64_windows_backend
from .base import CodeGeneratorBackend

__all__ = [
    "CodeGeneratorBackend",
    "generate_aarch64_lir_macos_backend",
    "generate_aarch64_macos_backend",
    "generate_amd64_linux_backend",
    "generate_amd64_windows_backend",
]
