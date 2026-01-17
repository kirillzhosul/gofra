from collections.abc import Sequence

from libgofra.exceptions import GofraError
from libgofra.types._base import Type


class EntryPointParametersMismatchTypecheckError(GofraError):
    def __init__(
        self,
        *args: object,
        parameters: Sequence[Type],
        entry_point_name: str,
    ) -> None:
        super().__init__(*args)
        self.parameters = parameters
        self.entry_point_name = entry_point_name

    def __repr__(self) -> str:
        return f"""Entry point function '{self.entry_point_name}' violates parameters type contract!

Entry point function cannot accept any parameters!
But currently it has parameters: {self.parameters}
"""
