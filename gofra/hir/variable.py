from dataclasses import dataclass
from enum import Enum, auto

from gofra.lexer.tokens import TokenLocation
from gofra.types._base import Type


@dataclass(frozen=True, slots=True)
class Variable:
    """HIR variable containing an name and type."""

    # Actual name of the variable as defined in source code.
    name: str

    # Source location of definition
    defined_at: TokenLocation

    # LIR (code-generation) hint about where to locate that variable
    storage_class: "VariableStorageClass"

    # Where this variable is located: top level global scope, or function (mostly) local scope
    scope_class: "VariableScopeClass"

    # Type of an variable specified in source code
    type: Type

    def __post_init__(self) -> None:
        """Validate variable container, must not raise any errors as must be handled outside of that."""
        if self.is_global_scope and self.storage_class != VariableStorageClass.STATIC:
            msg = "Global scope variables must have static storage class"
            raise ValueError(msg)

    @property
    def is_global_scope(self) -> bool:
        """Is this variable defined in global root scope."""
        return self.scope_class == VariableScopeClass.GLOBAL

    @property
    def is_function_scope(self) -> bool:
        """Is this variable defined in function owned scope."""
        return self.scope_class == VariableScopeClass.FUNCTION

    @property
    def size_in_bytes(self) -> int:
        """Size in bytes that is required to allocate this variable somewhere."""
        return self.type.size_in_bytes


class VariableStorageClass(Enum):
    """Hint for code-generation where to locate that variable."""

    # stack - locate on stack, function locals only
    STACK = auto()

    # static - locate globally in data section, globals only
    STATIC = auto()


class VariableScopeClass(Enum):
    """Location of definition for that variable (e.g owner scope)."""

    # Top level scope - global in root of the program
    GLOBAL = auto()

    # Function scope - owner is an function and mostly has VariableStorageClass.STACK
    FUNCTION = auto()
