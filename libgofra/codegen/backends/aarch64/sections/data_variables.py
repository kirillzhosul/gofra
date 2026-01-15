from __future__ import annotations

from typing import TYPE_CHECKING

from libgofra.codegen.sections._factory import SectionType
from libgofra.hir.initializer import (
    VariableIntArrayInitializerValue,
    VariableIntFieldedStructureInitializerValue,
    VariableStringPtrArrayInitializerValue,
    VariableStringPtrInitializerValue,
)
from libgofra.types._base import PrimitiveType
from libgofra.types.composite.array import ArrayType
from libgofra.types.composite.pointer import PointerType
from libgofra.types.composite.string import StringType
from libgofra.types.composite.structure import StructureType
from libgofra.types.primitive.character import CharType
from libgofra.types.primitive.integers import I64Type

if TYPE_CHECKING:
    from collections.abc import Mapping

    from libgofra.codegen.backends.aarch64._context import AARCH64CodegenContext
    from libgofra.hir.variable import Variable
    from libgofra.types._base import Type


def write_initialized_data_section(
    context: AARCH64CodegenContext,
    strings: Mapping[str, str],
    variables: Mapping[str, Variable[Type]],
) -> None:
    """Initialize data section fields with given values.

    Section is an tuple (label, data)
    Data is an string (raw ASCII) or number (zeroed memory blob)
    """
    variables = {k: v for k, v in variables.items() if v.initial_value is not None}

    if not variables and not strings:
        return

    context.section(SectionType.DATA)
    for name, variable in variables.items():
        _write_static_segment_const_variable_initializer(
            context,
            variable,
            symbol_name=name,
        )

    for name, data in strings.items():
        context.fd.write(".p2align 3\n")
        decoded_string = data.encode().decode("unicode_escape")
        length = len(decoded_string)
        context.fd.write(f"{name}: \n\t.quad {name}d\n\t.quad {length}\n")


def _write_static_segment_const_variable_initializer(
    context: AARCH64CodegenContext,
    variable: Variable[Type],
    symbol_name: str,
) -> None:
    type_size = variable.size_in_bytes

    assert variable.initial_value is not None
    match variable.type:
        case CharType() | I64Type():
            assert isinstance(variable.initial_value, int)
            if type_size == 0:
                context.on_warning(
                    f"Variable {variable.name} has zero byte size (type {variable.type}) this variable will be not defined as symbol!",
                )
                return
            # TODO(@kirillzhosul): review realignment of static variables
            if type_size >= 32:
                context.fd.write(".p2align 4\n")
            else:
                context.fd.write(".p2align 3\n")

            ddd = _get_ddd_for_type(variable.type)
            context.fd.write(f"{symbol_name}: {ddd} {variable.initial_value}\n")
        case ArrayType(element_type=I64Type()):
            assert isinstance(variable.initial_value, VariableIntArrayInitializerValue)
            ddd = _get_ddd_for_type(I64Type())

            values = variable.initial_value.values
            f_values = ", ".join(map(str, values))

            context.fd.write(f"{symbol_name}: \n\t{ddd} {f_values}\n")
            assert variable.initial_value.default == 0, "Not implemented"
            if variable.initial_value.default == 0:
                # Zero initialized symbol
                # TODO(@kirillzhosul): Alignment
                assert variable.type.elements_count, "Got incomplete array type"
                element_size = variable.type.element_type.size_in_bytes
                bytes_total = variable.type.size_in_bytes
                bytes_taken = len(values) * element_size
                bytes_free = bytes_total - bytes_taken
                context.fd.write(f"\t.zero {bytes_free}\n")
        case ArrayType(element_type=PointerType(points_to=StringType())):
            assert isinstance(
                variable.initial_value,
                VariableStringPtrArrayInitializerValue,
            )

            values = variable.initial_value.values
            f_values = ", ".join(map(context.load_string, values))

            context.fd.write(f"{symbol_name}: \n\t.quad {f_values}\n")

        case PointerType(points_to=StringType()):
            assert isinstance(variable.initial_value, VariableStringPtrInitializerValue)
            string_raw = variable.initial_value.string
            context.fd.write(
                f"{symbol_name}: \n\t.quad {context.load_string(string_raw)}\n",
            )
        case StructureType():
            assert isinstance(
                variable.initial_value,
                VariableIntFieldedStructureInitializerValue,
            )
            # TODO(@kirillzhosul): Validate fields types before plain initialization
            context.fd.write(f"{symbol_name}: \n")
            for t_field_name, (init_field_name, init_field_value) in zip(
                variable.type.natural_order,
                variable.initial_value.values.items(),
                strict=True,
            ):
                # Must initialize in same order!
                assert t_field_name == init_field_name
                field_t = variable.type.get_field_type(t_field_name)
                assert isinstance(field_t, PrimitiveType)
                ddd = _get_ddd_for_type(field_t)
                context.fd.write(
                    f"\t{ddd} {init_field_value}\n",
                )
        case _:
            msg = f"Has no known initializer codegen logic for type {variable.type}"
            raise ValueError(msg)


def _get_ddd_for_type(t: PrimitiveType) -> str:
    """Get Data Definition Directive for type based on byte size."""
    type_size = t.size_in_bytes
    if type_size <= 1:
        return ".byte"
    if type_size <= 2:
        return ".half"
    if type_size <= 4:
        return ".word"
    if type_size <= 8:
        return ".quad"
    msg = f"Cannot get DDD for symbol of type {t}, max byte size is capped"
    raise ValueError(msg)
