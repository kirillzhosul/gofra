from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VariableIntArrayInitializerValue:
    """HIR value parsed from initializer for int array.

    Variable must be initialized with this value.
    """

    default: int
    values: list[int]


@dataclass(frozen=True, slots=True)
class VariableStringPtrArrayInitializerValue:
    """HIR value parsed from initializer for *string array.

    Variable must be initialized with this value.
    """

    default: int
    values: list[str]


@dataclass(frozen=True, slots=True)
class VariableIntFieldedStructureInitializerValue:
    """HIR value parsed from initializer for structure where all fields are integers and fulfilled."""

    values: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class VariableStringPtrInitializerValue:
    """HIR value parsed from initializer for string (e.g *string / string).

    Variable must be initialized with this value.
    """

    string: str


type T_AnyVariableInitializer = (
    int
    | VariableIntArrayInitializerValue
    | VariableStringPtrInitializerValue
    | VariableStringPtrArrayInitializerValue
    | VariableIntFieldedStructureInitializerValue
)
