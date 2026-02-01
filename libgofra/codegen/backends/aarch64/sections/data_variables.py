from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from libgofra.codegen.backends.string_pool import StringPool
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

    from libgofra.codegen.backends.aarch64.codegen import (
        AARCH64CodegenBackend,
    )
    from libgofra.hir.variable import Variable
    from libgofra.types._base import Type


def write_initialized_data_section(
    context: AARCH64CodegenBackend,
    strings: StringPool,
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
    alignment = None
    for name, variable in variables.items():
        if variable.type.alignment != alignment:
            context.directive("align", variable.type.alignment)
            alignment = variable.type.alignment
        _write_static_segment_variable_initializer(
            context,
            variable,
            symbol_name=name,
        )

    if strings:
        # 8 byte alignment for string descriptors
        context.directive("align", 8)

    for data, name in strings.get_view():
        decoded_string = data.encode().decode("unicode_escape")
        length = len(decoded_string)
        context.label(name)
        context.sym_sect_directive("quad", f"{name}d")
        context.sym_sect_directive("quad", length)


def _write_static_segment_variable_initializer(
    context: AARCH64CodegenBackend,
    variable: Variable[Type],
    symbol_name: str,
) -> None:
    type_size = variable.size_in_bytes
    assert type_size, (
        f"Variable {variable.name} defined at {variable.defined_at} has zero byte size (type {variable.type}) this variable will be not defined as symbol!"
    )

    assert variable.initial_value is not None
    match variable.type:
        case CharType() | I64Type():
            assert isinstance(variable.initial_value, int)
            ddd = _get_ddd_for_type(variable.type)
            context.label(symbol_name)
            context.sym_sect_directive(ddd, variable.initial_value)
        case ArrayType(element_type=I64Type()):
            assert isinstance(variable.initial_value, VariableIntArrayInitializerValue)
            ddd = _get_ddd_for_type(I64Type())

            values = variable.initial_value.values
            f_values = ", ".join(map(str, values))

            context.label(symbol_name)
            context.sym_sect_directive(ddd, f_values)
            # Zero initialized symbol
            element_size = variable.type.element_type.size_in_bytes
            empty_cells = variable.type.elements_count - len(values)
            if not empty_cells:
                return
            if variable.initial_value.default == 0:
                bytes_total = variable.type.size_in_bytes
                bytes_taken = len(values) * element_size
                bytes_free = bytes_total - bytes_taken
                context.sym_sect_directive("zero", bytes_free)

            else:
                fill_with = variable.initial_value.default
                cell_size = I64Type().size_in_bytes
                context.sym_sect_directive("fill", empty_cells, cell_size, fill_with)

                context.comment_eol(f"Filler ({fill_with})")

        case ArrayType(element_type=PointerType(points_to=StringType())):
            assert isinstance(
                variable.initial_value,
                VariableStringPtrArrayInitializerValue,
            )

            values = variable.initial_value.values
            f_values = ", ".join(map(context.string_pool.add, values))

            context.label(symbol_name)
            context.sym_sect_directive("quad", f_values)
        case PointerType(points_to=StringType()):
            assert isinstance(variable.initial_value, VariableStringPtrInitializerValue)
            string_raw = variable.initial_value.string
            context.label(symbol_name)
            context.sym_sect_directive("quad", context.string_pool.add(string_raw))
        case StructureType():
            assert isinstance(
                variable.initial_value,
                VariableIntFieldedStructureInitializerValue,
            )
            _write_static_segment_structure_initializer(
                context,
                struct=variable.type,
                initial_value=variable.initial_value,
                symbol_name=symbol_name,
            )
        case _:
            msg = f"Has no known static initializer codegen logic for type {variable.type}"
            raise ValueError(msg)


def _write_static_segment_structure_initializer(
    context: AARCH64CodegenBackend,
    symbol_name: str,
    struct: StructureType,
    initial_value: VariableIntFieldedStructureInitializerValue,
) -> None:
    context.label(symbol_name)
    context.comment_eol(repr(struct))
    prev_taken_bytes = 0
    for field in struct.order:
        value = initial_value.values[field]

        field_t = struct.get_field_type(field)
        assert isinstance(field_t, PrimitiveType), field_t

        padding = struct.get_field_offset(field) - prev_taken_bytes

        ddd = _get_ddd_for_type(field_t)
        if padding:
            context.sym_sect_directive("zero", padding)
            context.comment_eol("[[padding]]")

        context.sym_sect_directive(ddd, value)
        context.comment_eol(f"{struct.name}.{field}")

        prev_taken_bytes += field_t.size_in_bytes + padding


def _get_ddd_for_type(t: PrimitiveType) -> Literal["byte", "half", "word", "quad"]:
    """Get Data Definition Directive for type based on byte size."""
    type_size = t.size_in_bytes
    if type_size <= 1:
        return "byte"
    if type_size <= 2:
        return "half"
    if type_size <= 4:
        return "word"
    if type_size <= 8:
        return "quad"
    msg = f"Cannot get DDD for symbol of type {t}, max byte size is capped"
    raise ValueError(msg)
