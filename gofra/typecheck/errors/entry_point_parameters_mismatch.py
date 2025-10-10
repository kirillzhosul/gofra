from collections.abc import Sequence

from gofra.consts import GOFRA_ENTRY_POINT
from gofra.exceptions import GofraError
from gofra.types._base import Type


class EntryPointParametersMismatchTypecheckError(GofraError):
    def __init__(self, *args: object, parameters: Sequence[Type]) -> None:
        super().__init__(*args)
        self.parameters = parameters

    def __repr__(self) -> str:
        return f"""Entry point function '{GOFRA_ENTRY_POINT}' violates parameters type contract!

Entry point function cannot accept any parameters!
But currently it has parameters: {self.parameters}
"""
