"""Preprocessor which resolves includes, CTE/macros and other from given lexer.

Simply, wraps an lexer into another `lexer` and preprocess on the fly.
"""

from .preprocessor import preprocess_file

__all__ = ("preprocess_file",)
