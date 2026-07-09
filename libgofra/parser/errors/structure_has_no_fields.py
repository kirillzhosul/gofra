from libgofra.exceptions import GofraError
from libgofra.lexer.tokens import TokenLocation
from libgofra.types.composite.structure import StructureType


class StructureHasNoFieldsError(GofraError):
    def __init__(self, structure: StructureType, at: TokenLocation) -> None:
        self.structure = structure
        self.at = at

    def __repr__(self) -> str:
        return f"""Structure {self.structure.name} has no fields.

Structure defined at {self.at}

Structures cannot have no fields as this implies their size will be zero!

{self.generic_error_name}"""
