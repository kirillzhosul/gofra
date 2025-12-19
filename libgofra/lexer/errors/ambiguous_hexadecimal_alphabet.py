from libgofra.exceptions import GofraError
from libgofra.lexer.tokens import TokenLocation


class AmbiguousHexadecimalAlphabetError(GofraError):
    def __init__(self, at: TokenLocation, number_raw: str) -> None:
        self.number_raw = number_raw
        self.at = at

    def __repr__(self) -> str:
        # TODO(@kirillzhosul): Ambiguous location
        return f"""Ambiguous hex (16-base) alphabet at {self.at}!

Invalid number: '{self.number_raw}'
Ambiguous symbol: XXX TBD 
Hexadecimal numbers must consist only from symbols of hex alphabet (0-Z)

{self.generic_error_name}"""
