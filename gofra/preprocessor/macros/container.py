from collections.abc import Generator
from dataclasses import dataclass

from gofra.lexer.tokens import Token


@dataclass(frozen=True)
class Macro:
    token: Token

    name: str

    tokens: list[Token]

    def as_tokenizer(self) -> Generator[Token]:
        yield from self.tokens
