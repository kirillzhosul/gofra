"""Lexer package that used to lex source text into tokens (e.g tokenization).

Lexer takes an input file and splits it content into tokens.

Tokens and lexer implemented a bit odd (https://en.wikipedia.org/wiki/Lexical_analysis)
Some token types are misleading, this code does not always imply conventions.
"""

from .exceptions import LexerError
from .keywords import Keyword
from .lexer import tokenize_file
from .tokens import Token, TokenType

__all__ = [
    "Keyword",
    "LexerError",
    "Token",
    "TokenType",
    "tokenize_file",
]
