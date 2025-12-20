from libgofra.exceptions import GofraError
from libgofra.lexer.tokens import TokenLocation


class UserDefinedCompileTimeError(GofraError):
    def __init__(self, at: TokenLocation, message: str) -> None:
        self.at = at
        self.message = message

    def __repr__(self) -> str:
        return f"""Compilation error with message '{self.message}' at {self.at}

This was raised from `compile_error` inside source code!

{self.generic_error_name}"""
