from libgofra.exceptions import GofraError
from libgofra.hir.variable import Variable
from libgofra.lexer.tokens import TokenLocation
from libgofra.types.composite.array import ArrayType


class ArrayOutOfBoundsError(GofraError):
    def __init__(
        self,
        array_index_at: int,
        at: TokenLocation,
        variable: Variable[ArrayType],
    ) -> None:
        self.array_index_at = array_index_at
        self.at = at
        self.variable = variable

    def __repr__(self) -> str:
        return f"""Out-of-bounds array access at {self.at}

{self.variable.name}[{self.array_index_at}] is not within type of {self.variable.name} ({self.variable.type})
Note: Variable defined at {self.variable.defined_at}

{self.generic_error_name}"""
