from libgofra.exceptions import GofraError
from libgofra.lexer.tokens import TokenLocation


class LambdaWithExternAttrError(GofraError):
    def __init__(self, at: TokenLocation) -> None:
        self.at = at

    def __repr__(self) -> str:
        return f"""Lambdas cannot have extern attribute!

Tried to use `extern` attribute at {self.at}, which is prohibited!
Lambdas cannot be extern, as this makes no sense

{self.generic_error_name}"""
