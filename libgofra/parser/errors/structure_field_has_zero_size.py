from libgofra.exceptions import GofraError
from libgofra.lexer.tokens import TokenLocation
from libgofra.types._base import Type
from libgofra.types.composite.structure import StructureType


class StructureFieldHasZeroError(GofraError):
    def __init__(
        self,
        structure: StructureType,
        at: TokenLocation,
        field_type: Type,
        field_name: str,
    ) -> None:
        self.structure = structure
        self.field_type = field_type
        self.field_name = field_name
        self.at = at

    def __repr__(self) -> str:
        return f"""Structure {self.structure.name} has field '{self.field_name}' with zero size.

Field type is {self.field_type} which size is zero.
Structure defined at {self.at}

{self.generic_error_name}"""
