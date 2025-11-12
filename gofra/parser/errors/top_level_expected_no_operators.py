from gofra.exceptions import GofraError
from gofra.hir.operator import Operator


class TopLevelExpectedNoOperatorsError(GofraError):
    def __init__(self, operator: Operator) -> None:
        self.operator = operator

    def __repr__(self) -> str:
        return f"""Expected no operators at top-level

Operators cannot appear at top-level, they must appear inside local scopes (e.g functions)
First operator at top level was found here: {self.operator.location}

{self.generic_error_name}"""
