from libgofra.exceptions import GofraError
from libgofra.lexer.tokens import TokenLocation


class ReadOnlyMemoryAssignmentError(GofraError):
    """Raised when a write operation is attempted on a pointer marked as STATIC_READONLY."""

    def __init__(self, at: TokenLocation) -> None:
        self.at = at

    def __repr__(self) -> str:
        return f"""Illegal assignment to read-only memory!

The operation at {self.at} attempted to write data to read only memory.
This memory is located in a STATIC_READONLY segment, 
which is hardware-protected against writes at runtime.

{self.generic_error_name}"""
