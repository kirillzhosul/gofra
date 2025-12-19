"""Input/Output (IO) helpers for filesystem within toolchain.

It is an part of lexer due to toolchain built on top of lexer (as entry point to parser) and opening an file is responsibility of lexer.
"""

from .io import open_source_file, open_source_file_line_stream

__all__ = ("open_source_file", "open_source_file_line_stream")
