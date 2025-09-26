from dataclasses import dataclass

from gofra.typecheck.types import GofraType


class ComplexType: ...


@dataclass
class ArrayType(ComplexType):
    primitive_type: GofraType
    size_in_elements: int


@dataclass
class Variable:
    name: str
    type: GofraType | ArrayType
