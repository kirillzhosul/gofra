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

    # TODO(@kirillzhosul): Static class for local variables - https://github.com/kirillzhosul/gofra/issues/25
    # TODO(@kirillzhosul): Register class for local variables - https://github.com/kirillzhosul/gofra/issues/26


class VariableScopeClass(Enum):
    """Location of the definition of that variable (e.g owner scope/context)."""

    # Top level scope - global in root of the program (no owner function)
    GLOBAL = auto()

    # Function scope - owner is an function and mostly has VariableStorageClass.STACK
    FUNCTION = auto()
