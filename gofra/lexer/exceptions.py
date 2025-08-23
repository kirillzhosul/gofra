from string import hexdigits

from gofra.exceptions import GofraError
from gofra.lexer.helpers import HEXADECIMAL_MARK

from .tokens import TokenLocation


class LexerError(GofraError):
    """General error within lexer.

    Should not be used directly as not provides information about error source!
    """

    def __repr__(self) -> str:
        return """General lexer error occurred. 

Please open an issue about that undocumented behavior!
"""


class LexerAmbigiousHexadecimalAlphabetError(LexerError):
    def __init__(
        self,
        *args: object,
        hexadecimal_raw: str,
        number_location: TokenLocation,
    ) -> None:
        super().__init__(*args)
        self.number_location = number_location
        self.hexadecimal_raw = hexadecimal_raw

    def __repr__(self) -> str:
        return f"""Ambigious hexadecimal alphabet inside '{self.hexadecimal_raw}' at {self.number_location}!

Hexadecimal numbers ({HEXADECIMAL_MARK}) must consinst of 16-base alphabet ({hexdigits})"""


class LexerUnclosedCharacterQuoteError(LexerError):
    def __init__(self, *args: object, open_quote_location: TokenLocation) -> None:
        super().__init__(*args)
        self.open_quote_location = open_quote_location

    def __repr__(self) -> str:
        return f"""Unclosed character quote at {self.open_quote_location}!

Did you forgot to close an character?"""


class LexerExcessiveCharacterLengthError(LexerError):
    def __init__(
        self,
        *args: object,
        excess_begins_at: TokenLocation,
        excess_by_count: int,
    ) -> None:
        super().__init__(*args)
        self.excess_begins_at = excess_begins_at
        self.excess_by_count = excess_by_count

    def __repr__(self) -> str:
        return f"""Excessive amount of symbols in character at {self.excess_begins_at}!

Expected only one symbol in character but got {self.excess_by_count}!

Did you accidentally mix up characters and strings?"""


class LexerEmptyCharacterError(LexerError):
    def __init__(self, *args: object, open_quote_location: TokenLocation) -> None:
        super().__init__(*args)
        self.open_quote_location = open_quote_location

    def __repr__(self) -> str:
        return f"""Empty character at {self.open_quote_location}!

Expected single symbol in character!

Did you forgot to enter an character?"""


class LexerUnclosedStringQuoteError(LexerError):
    def __init__(
        self,
        *args: object,
        open_quote_location: TokenLocation,
    ) -> None:
        super().__init__(*args)
        self.open_quote_location = open_quote_location

    def __repr__(self) -> str:
        return f"""Unclosed string quote at {self.open_quote_location}

Did you forgot to close string or mistyped string quote?"""
