from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum, auto

from libgofra.types._base import Type
from libgofra.types.composite.array import ArrayType
from libgofra.types.composite.function import FunctionType
from libgofra.types.composite.pointer import PointerType
from libgofra.types.composite.structure import StructureType


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

    def __hash__(self) -> int:
        return hash(self.name)


@dataclass
class GenericArrayType(GenericParametrizedType):
    element_type: GenericParametrizedType | Type
    element_count: GenericParameter | int


@dataclass
class GenericFunctionType(GenericParametrizedType):
    return_value: Type | GenericParametrizedType
    parameters: Sequence[Type | GenericParametrizedType]

    def __repr__(self) -> str:
        return f"({', '.join(map(repr, self.parameters))}) -> {self.return_value}"


class GenericStructureType(GenericParametrizedType):
    """Type that holds fields with their types as structure."""

    # Direct mapping from name of the field to its direct type
    fields: Mapping[str, Type | GenericParametrizedType]

    # Order of name for offsetting in `fields`, as mapping does not contain any order information
    fields_ordering: Sequence[str]

    name: str

    # Propagated attributes to concrete structure
    is_packed: bool
    reorder: bool

    def __init__(
        self,
        name: str,
        fields: Mapping[str, Type],
        fields_ordering: Sequence[str],
        *,
        is_packed: bool,
        reorder: bool = False,
    ) -> None:
        self.name = name
        self.fields = fields
        self.fields_ordering = fields_ordering
        self.is_packed = is_packed
        self.reorder = reorder

    def __repr__(self) -> str:
        return f"Generic Struct {self.name}"


@dataclass
class GenericPointerType(GenericParametrizedType):
    points_to: GenericParametrizedType | Type

    def __repr__(self) -> str:
        return f"*Generic {self.points_to!r}"


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
            if generic.name not in type_parameters:
                msg = f"Generic param {generic.name} does not exists in type parameters {type_parameters}"
                raise ValueError(msg)
            t = type_parameters[generic.name]
            assert isinstance(t, Type)
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
                    msg = f"Parameter of generic with typename '{generic.element_count.name}' has '{generic.element_count.kind.name}' kind but got an 'VALUE PARAM', cannot apply generic into concrete type \n[error-location-cannot-be-propagated]"
                    raise TypeError(msg)

            return ArrayType(
                element_type=concrete_element_type,
                elements_count=concrete_elements_count,
            )
        case GenericStructureType():
            concrete_fields = {
                name: apply_generic_type_into_concrete(field_t, type_parameters)
                if isinstance(field_t, GenericParametrizedType)
                else field_t
                for name, field_t in generic.fields.items()
            }
            return StructureType(
                name=f"=mangled_concrete_generic_{generic.name}",  # TODO: Failure intolerant
                fields=concrete_fields,
                order=generic.fields_ordering,
                is_packed=generic.is_packed,
                reorder=generic.reorder,
            )
        case GenericFunctionType():
            concrete_return_type = (
                apply_generic_type_into_concrete(generic.return_value, type_parameters)
                if isinstance(generic.return_value, GenericParametrizedType)
                else generic.return_value
            )
            concrete_params = [
                (
                    apply_generic_type_into_concrete(p, type_parameters)
                    if isinstance(p, GenericParametrizedType)
                    else p
                )
                for p in generic.parameters
            ]
            return FunctionType(
                parameter_types=concrete_params,
                return_type=concrete_return_type,
            )
        case _:
            msg = f"Cannot {apply_generic_type_into_concrete.__name__} for {generic}!"
            raise ValueError(msg)


def get_generic_type_parameters_count(t: GenericParametrizedType | Type) -> int:
    return len(get_generic_type_parameters(t))


def get_generic_type_parameters(
    t: GenericParametrizedType | Type,
) -> set[GenericParameter]:
    match t:
        case GenericPointerType():
            return get_generic_type_parameters(t.points_to)
        case GenericArrayType():
            tp: set[GenericParameter] = set()
            if not isinstance(t.element_count, int):
                tp.add(t.element_count)
            if isinstance(t.element_type, GenericParametrizedType):
                tp.update(get_generic_type_parameters(t.element_type))
            return tp
        case GenericParameter():
            return {t}
        case GenericStructureType():
            tp: set[GenericParameter] = set()
            for f in t.fields.values():
                tp.update(get_generic_type_parameters(f))
            return tp

        case _:
            return set()
