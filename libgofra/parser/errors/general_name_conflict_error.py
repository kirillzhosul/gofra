from libgofra.exceptions import GofraError
from libgofra.hir.function import Function
from libgofra.hir.variable import Variable
from libgofra.types._base import Type
from libgofra.types.composite.structure import StructureType
from libgofra.types.generics import GenericParametrizedType

type HOLDER_T = (
    StructureType | Function | Variable[Type] | Type | GenericParametrizedType | str
)


class GeneralNameHolderConflictError(GofraError):
    def __init__(
        self,
        name_holder: HOLDER_T,
        conflicting_holder: HOLDER_T,
    ) -> None:
        self.conflicting_holder = conflicting_holder
        self.name_holder = name_holder

    def repr_name_holder(self, holder: HOLDER_T) -> str:
        match holder:
            case Function():
                return f"Function '{holder.name}' defined at {holder.defined_at}"
            case Variable():
                return f"Variable '{holder.name}' defined at {holder.defined_at}"
            case str():
                return holder
            case _:
                return repr(holder)

    def __repr__(self) -> str:
        return f"""{self.repr_name_holder(self.conflicting_holder)} tried to redefined original name holder!

Conflicts with name holder: {self.repr_name_holder(self.name_holder)}

{self.generic_error_name}"""
