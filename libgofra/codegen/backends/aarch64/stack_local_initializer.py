"""Assembly abstraction layer that hides declarative assembly OPs into functions that generates that for you."""

from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from libgofra.codegen.backends.aarch64.primitive_instructions import (
    AddressingMode,
    get_address_of_label,
)
from libgofra.codegen.backends.aarch64.writer import WriterProtocol
from libgofra.codegen.backends.frame import build_local_variables_frame_offsets
from libgofra.codegen.backends.string_pool import StringPool
from libgofra.hir.initializer import (
    T_AnyVariableInitializer,
    VariableIntArrayInitializerValue,
    VariableIntFieldedStructureInitializerValue,
    VariableStringPtrArrayInitializerValue,
    VariableStringPtrInitializerValue,
)
from libgofra.types.composite.array import ArrayType
from libgofra.types.composite.pointer import PointerType

if TYPE_CHECKING:
    from collections.abc import Mapping

    from libgofra.hir.variable import Variable
    from libgofra.types._base import Type


def write_function_local_stack_variables_initializer(
    writer: WriterProtocol,
    string_pool: StringPool,
    *,
    local_variables: Mapping[str, Variable[Type]],
) -> None:
    local_offsets = build_local_variables_frame_offsets(local_variables)
    for variable in local_variables.values():
        initial_value = variable.initial_value
        if initial_value is None:
            continue

        current_offset = local_offsets.offsets[variable.name]
        _write_initializer_for_stack_variable(
            writer,
            initial_value,
            string_pool,
            variable.type,
            current_offset,
        )


def _write_initializer_for_stack_variable(
    writer: WriterProtocol,
    initial_value: T_AnyVariableInitializer,
    string_pool: StringPool,
    var_type: Type,
    offset: int,
) -> None:
    assert offset > 0

    if isinstance(initial_value, int):
        return _set_local_numeric_var_immediate(
            writer,
            initial_value,
            var_type,
            offset,
        )

    if isinstance(initial_value, VariableIntArrayInitializerValue):
        assert isinstance(var_type, ArrayType)
        values = initial_value.values
        setters = ((var_type.get_index_offset(i), v) for i, v in enumerate(values))
        for relative_offset, value in setters:
            _set_local_numeric_var_immediate(
                writer,
                value,
                var_type.element_type,
                offset=offset + relative_offset,
            )
        return None

    if isinstance(initial_value, VariableStringPtrInitializerValue):
        # Load string as static string and dispatch pointer on entry
        static_blob_sym = string_pool.add(initial_value.string)
        assert isinstance(var_type, PointerType)
        get_address_of_label(writer, "X0", static_blob_sym, mode=AddressingMode.PAGE)
        writer.instruction(f"str X0, [X29, -{offset}]")
        return None

    if isinstance(
        initial_value,
        VariableIntFieldedStructureInitializerValue
        | VariableStringPtrArrayInitializerValue,
    ):  # pyright: ignore[reportUnnecessaryIsInstance]
        msg = f"{initial_value} is not implemented on-stack within codegen"
        raise NotImplementedError(msg)

    assert_never(initial_value)


def _set_local_numeric_var_immediate(
    writer: WriterProtocol,
    value: int,
    t: Type,
    offset: int,
) -> None:
    """Set immediate numeric value for local variable at given offset. Respects memory store instructions."""
    assert 0 < t.size_in_bytes <= 8, "Too big type to store into"

    # Use half-word instruction set (W register, half store)
    is_hword = t.size_in_bytes <= 4
    bit_count = 8 * t.size_in_bytes
    sr = ("XZR", "WZR")[is_hword] if value == 0 else ("X0", "W0")[is_hword]

    if sr in ("X0", "W0"):
        assert value.bit_count() <= bit_count
        writer.instruction(f"mov {sr}, #{value}")

    instr = "strb" if t.size_in_bytes == 1 else ("strh" if is_hword else "str")
    writer.instruction(f"{instr} {sr}, [X29, -{offset}]")
