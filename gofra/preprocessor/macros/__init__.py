"""Preprocessor macros parser/resolver."""

from .container import Macro
from .preprocessor import define_macro_block_from_token

__all__ = ("Macro", "define_macro_block_from_token")
