from libgofra.exceptions import GofraError
from libgofra.lexer.tokens import Token, TokenLocation


class TestkitExpectedExitCodeMustBeIntError(GofraError):
    def __init__(self, at: TokenLocation, token: Token) -> None:
        self.at = at
        self.token = token

    def __repr__(self) -> str:
        return f"""Expected TESTKIT_EXPECTED_EXIT_CODE to be an integer at {self.at}.

But got {self.token.type.name} which is not an integer. Please provide an integer value for TESTKIT_EXPECTED_EXIT_CODE.

{self.generic_error_name}"""
