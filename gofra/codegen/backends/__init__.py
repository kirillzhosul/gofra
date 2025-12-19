"""Code generation backend module.

Provides code generation backends (codegen) for emitting assembly from IR.
"""

from .aarch64.codegen import AARCH64CodegenBackend
from .amd64.codegen import AMD64CodegenBackend
from .base import CodeGeneratorBackend

__all__ = [
    "AARCH64CodegenBackend",
    "AMD64CodegenBackend",
    "CodeGeneratorBackend",
]
