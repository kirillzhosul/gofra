from libgofra.exceptions import GofraError
from libgofra.types._base import Type


class EntryPointReturnTypeMismatchTypecheckError(GofraError):
    def __init__(self, *args: object, return_type: Type, entry_point_name: str) -> None:
        super().__init__(*args)
        self.return_type = return_type
        self.entry_point_name = entry_point_name

    def __repr__(self) -> str:
        return f"""Entry point function '{self.entry_point_name}' violates return type contract!

Entry point function cannot have type contract out (e.g only `void` and `int` type is allowed)!
But currently it has return type: {self.return_type}
"""
