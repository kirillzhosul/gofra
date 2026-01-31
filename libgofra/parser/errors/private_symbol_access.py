from libgofra.exceptions import GofraError
from libgofra.lexer.tokens import TokenLocation


class PrivateSymbolAccessError(GofraError):
    """Raised when an internal/private function is accessed from an external module."""

    def __init__(
        self,
        symbol_name: str,
        defined_at: TokenLocation,
        call_site: TokenLocation,
        target_module: str,
    ) -> None:
        self.symbol_name = symbol_name
        self.defined_at = defined_at
        self.call_site = call_site
        self.target_module = target_module

    def __repr__(self) -> str:
        return f"""Illegal access to private symbol!

The call at {self.call_site} attempted to invoke the internal function '{self.symbol_name}'.
This symbol is private to module '{self.target_module}' and is not exported.

Symbol defined at: {self.defined_at}

Visibility Violation:
Either mark '{self.symbol_name}' as public in its home module or avoid using 
prohibited internal symbols from external modules.

{self.generic_error_name}"""
