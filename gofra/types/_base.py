from typing import Protocol, runtime_checkable


@runtime_checkable
class Type(Protocol):
    """Base type for Gofra.

    Any type is children of that class, but they are splitted into 2 sub-types (Primitive and Composite type)
    """

    size_in_bytes: int

    is_fp: bool = False


# Base class for Primitive | Composite types
class PrimitiveType(Type): ...


class CompositeType(Type): ...
