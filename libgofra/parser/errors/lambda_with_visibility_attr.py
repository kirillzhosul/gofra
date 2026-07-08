from libgofra.exceptions import GofraError
from libgofra.lexer.tokens import TokenLocation


class LambdaWithVisibilityAttrError(GofraError):
    def __init__(self, at: TokenLocation) -> None:
        self.at = at

    def __repr__(self) -> str:
        return f"""Lambdas cannot have visibility attribute!

Tried to change visibility attribute at {self.at}, which is prohibited!
Lambdas always will be private

{self.generic_error_name}"""
