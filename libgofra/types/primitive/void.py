from libgofra.types._base import PrimitiveType


class VoidType(PrimitiveType):
    """Type that contains nothing, has no effect at runtime, rather compile-time and typechecker helper.

    E.g function that does not return any value has retval of type VOID,
    cogeneration can skip retval according to that as resolving that return value will mostly lead in stack corruption
    """

    size_in_bytes = 0

    def __repr__(self) -> str:
        return "VOID"
