from collections.abc import Mapping
from dataclasses import dataclass

from gofra.types._base import Type
from gofra.types.composite.pointer import PointerType


class GenericParametrizedType:
    """Any non concrete abstract type that must be parametrized into concrete one."""


@dataclass
class GenericParameter(GenericParametrizedType):
    name: str

    def __repr__(self) -> str:
        return f"'Type Param {self.name}'"


@dataclass
class GenericArrayType(GenericParametrizedType):
    element_type: GenericParametrizedType | Type
    element_count: int


@dataclass
class GenericPointerType(GenericParametrizedType):
    points_to: GenericParametrizedType | Type

    def __repr__(self) -> str:
        return f"*Generic {self.points_to.__repr__()}"


def apply_generic_type_into_concrete(
    generic: GenericParametrizedType,
    type_parameters: Mapping[str, Type],
) -> Type:
    """Instantiate generic parametrized type into concrete type with type parameters substitution.

    Given `IdentityGeneric<T> = T`, when TP `T=int`
    transform into concrete type `int`
    """
    match generic:
        case GenericPointerType():
            concrete_points_to: Type
            if isinstance(generic.points_to, Type):
                concrete_points_to = generic.points_to  # NOTE: Concrete
            else:
                concrete_points_to = apply_generic_type_into_concrete(
                    generic.points_to,
                    type_parameters,
                )
            return PointerType(points_to=concrete_points_to)
        case GenericParameter():
            return type_parameters[generic.name]
        case _:
            msg = f"Cannot get {get_generic_type_parameters_count.__name__} for {generic}!"
            raise ValueError(msg)


def get_generic_type_parameters_count(t: GenericParametrizedType | Type) -> int:
    match t:
        case GenericPointerType():
            return get_generic_type_parameters_count(t.points_to)
        case GenericArrayType():
            return get_generic_type_parameters_count(t.element_type)
        case GenericParameter():
            return 1
        case _:
            msg = f"Cannot get {get_generic_type_parameters_count.__name__}!"
            raise ValueError(msg)
