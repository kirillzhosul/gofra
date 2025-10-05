"""Gofra programming language.

Provides toolchain including CLI, compiler etc.
"""

from .assembler import assemble_object
from .gofra import process_input_file

__all__ = [
    "assemble_object",
    "process_input_file",
]
