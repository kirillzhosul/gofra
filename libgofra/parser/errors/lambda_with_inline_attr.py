from libgofra.exceptions import GofraError
from libgofra.lexer.tokens import TokenLocation


class LambdaWithInlineAttrError(GofraError):
    def __init__(self, at: TokenLocation) -> None:
        self.at = at

    def __repr__(self) -> str:
        return f"""Lambdas cannot have inline attribute!

Tried to use `inline` attribute at {self.at}, which is prohibited!
Lambdas cannot be inline, as this makes no sense

{self.generic_error_name}"""
