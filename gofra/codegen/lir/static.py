from dataclasses import dataclass
from typing import Protocol

from gofra.types._base import Type


class LIRStaticSegment(Protocol):
    name: str


@dataclass
class LIRStaticSegmentCString(LIRStaticSegment):
    name: str
    text: str

    def __repr__(self) -> str:
        return f"Static C-String '{self.name}'"


@dataclass
class LIRStaticSegmentGlobalVariable(LIRStaticSegment):
    name: str
    type: Type

    def __repr__(self) -> str:
        return f"Static global variable {self.type} '{self.name}'"
