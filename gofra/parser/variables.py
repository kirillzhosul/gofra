from dataclasses import dataclass

from gofra.types import Type


@dataclass
class Variable:
    name: str
    type: Type
