from __future__ import annotations

from typing import TYPE_CHECKING

from libgofra.codegen.backends.aarch64.sections import (
    write_initialized_data_section,
    write_text_string_section,
    write_uninitialized_data_section,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from libgofra.codegen.backends.aarch64._context import AARCH64CodegenContext
    from libgofra.hir.module import Module
    from libgofra.hir.variable import Variable
    from libgofra.types._base import Type


def aarch64_data_section(
    context: AARCH64CodegenContext,
    program: Module,
) -> None:
    """Write program static data section filled with static strings and memory blobs."""
    initialize_static_data_section(
        context,
        static_strings=context.strings,
        static_variables=program.variables,
    )


def initialize_static_data_section(
    context: AARCH64CodegenContext,
    static_strings: Mapping[str, str],
    static_variables: Mapping[str, Variable[Type]],
) -> None:
    """Initialize data section fields with given values.

    Section is an tuple (label, data)
    Data is an string (raw ASCII) or number (zeroed memory blob)
    """
    write_uninitialized_data_section(context, static_variables)
    write_initialized_data_section(context, static_strings, static_variables)
    # Must defined after others - string initializer may forward reference them
    # but we define them by single-pass within writing initializer
    write_text_string_section(context, static_strings, reference_suffix="d")
