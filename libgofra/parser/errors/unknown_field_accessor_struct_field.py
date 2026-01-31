from libgofra.exceptions import GofraError
from libgofra.lexer.tokens import TokenLocation
from libgofra.types.composite.structure import StructureType


class UnknownFieldAccessorStructFieldError(GofraError):
    def __init__(self, field: str, at: TokenLocation, struct: StructureType) -> None:
        self.field = field
        self.at = at
        self.struct = struct

    def __repr__(self) -> str:
        return f"""Unknown field accessor!

Trying to access field with name '{self.field} at {self.at} but it is not known within structure with name {self.struct.name}
Known fields: {", ".join(self.struct.natural_fields.keys())}
{self.generic_error_name}"""
