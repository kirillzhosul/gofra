from libgofra.exceptions import GofraError
from libgofra.lexer.tokens import TokenLocation
from libgofra.types.composite.structure import StructureType


class StructureHasZeroSizeError(GofraError):
    def __init__(self, structure: StructureType, at: TokenLocation) -> None:
        self.structure = structure
        self.at = at

    def __repr__(self) -> str:
        return f"""Structure {self.structure.name} has zero size.

Structure defined at {self.at}

If you define self-reference type, this leaded to infinite size (0 == inf in type)

{self.generic_error_name}"""
