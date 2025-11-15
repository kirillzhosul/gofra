from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, auto

from gofra.types._base import Type
from gofra.types.composite.array import ArrayType
from gofra.types.composite.pointer import PointerType


class GenericParametrizedType:
    """Any non concrete abstract type that must be parametrized into concrete one."""


@dataclass
class GenericParameter(GenericParametrizedType):
    class Kind(Enum):  # noqa: D106
        TYPE_PARAM = auto()  # Any type
        VALUE_PARAM = auto()  # Any int value

    name: str
    kind: Kind

    def __repr__(self) -> str:
        if self.kind == GenericParameter.Kind.TYPE_PARAM:
            return f"'Type Param {self.name}'"
        return f"'Type Value Param {self.name}'"


@dataclass
class GenericArrayType(GenericParametrizedType):
    element_type: GenericParametrizedType | Type
    element_count: GenericParameter | int


@dataclass
class GenericPointerType(GenericParametrizedType):
    points_to: GenericParametrizedType | Type

    def __repr__(self) -> str:
        return f"*Generic {self.points_to.__repr__()}"


def apply_generic_type_into_concrete(
    generic: GenericParametrizedType,
    type_parameters: Mapping[str, Type | int],
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
            assert generic.kind == GenericParameter.Kind.TYPE_PARAM, (
                "Got unfolded generic non type-param!"
            )
            t = type_parameters[generic.name]
            assert not isinstance(t, int)
            return t
        case GenericArrayType():
            concrete_element_type = (
                generic.element_type
                if isinstance(generic.element_type, Type)
                else apply_generic_type_into_concrete(
                    generic.element_type,
                    type_parameters,
                )
            )
            if isinstance(generic.element_count, int):
                concrete_elements_count = (
                    generic.element_count
                )  # Always concrete defined at generic definition
            else:
                # Generic VALUE param from application
                concrete_elements_count = type_parameters[generic.element_count.name]
                if not isinstance(concrete_elements_count, int):
                    msg = f"Parameter of generic with typename '{generic.element_count.name} [Kind={generic.element_count.kind.name}] is 'value param' (not 'type value') but got non a type (probably), cannot apply generic into concrete type \n[error-location-cannot-be-propagated]"
                    raise TypeError(msg)

            return ArrayType(
                element_type=concrete_element_type,
                elements_count=concrete_elements_count,
            )
        case _:
            msg = f"Cannot get {get_generic_type_parameters_count.__name__} for {generic}!"
            raise ValueError(msg)


def get_generic_type_parameters_count(t: GenericParametrizedType | Type) -> int:
    match t:
        case GenericPointerType():
            return get_generic_type_parameters_count(t.points_to)
        case GenericArrayType():
            elements_count_is_generic = not isinstance(t.element_count, int)
            return (
                get_generic_type_parameters_count(t.element_type)
                + elements_count_is_generic
            )
        case GenericParameter():
            return 1
        case _:
            msg = f"Cannot get {get_generic_type_parameters_count.__name__}!"
            raise ValueError(msg)
