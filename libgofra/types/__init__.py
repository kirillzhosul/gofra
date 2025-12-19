"""Type system for Gofra.

Does not contains any compile/run-time checks, only type definitions and system itself
Type may be used both in high-level like typecheck system or in low-level one as code generation
"""

from ._base import CompositeType, PrimitiveType, Type
from .composite import ArrayType, FunctionType, PointerType
from .primitive import BoolType, CharType, I64Type, VoidType

__all__ = [
    "ArrayType",
    "BoolType",
    "CharType",
    "CompositeType",
    "FunctionType",
    "I64Type",
    "PointerType",
    "PrimitiveType",
    "Type",
    "VoidType",
]
