"""Composite types for type system."""

from .array import ArrayType
from .function import FunctionType
from .pointer import PointerType

__all__ = ("ArrayType", "FunctionType", "PointerType")
