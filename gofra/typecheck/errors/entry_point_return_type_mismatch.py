from gofra.consts import GOFRA_ENTRY_POINT
from gofra.exceptions import GofraError
from gofra.types._base import Type


class EntryPointReturnTypeMismatchTypecheckError(GofraError):
    def __init__(self, *args: object, return_type: Type) -> None:
        super().__init__(*args)
        self.return_type = return_type

    def __repr__(self) -> str:
        return f"""Entry point function '{GOFRA_ENTRY_POINT}' violates return type contract!

Entry point function cannot have type contract out (e.g only `void` type is allowed)!
But currently it has return type: {self.return_type}
"""
