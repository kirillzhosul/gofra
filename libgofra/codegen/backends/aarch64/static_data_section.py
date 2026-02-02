from __future__ import annotations

from typing import TYPE_CHECKING

from libgofra.codegen.backends.aarch64.sections import (
    write_initialized_data_section,
    write_text_string_section,
    write_uninitialized_data_section,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from libgofra.codegen.backends.aarch64.writer import WriterProtocol
    from libgofra.codegen.backends.string_pool import StringPool
    from libgofra.hir.variable import Variable
    from libgofra.types._base import Type


def aarch64_data_section(
    writer: WriterProtocol,
    strings: StringPool,
    variables: Mapping[str, Variable[Type]],
) -> None:
    """Write program static data section filled with static strings and memory blobs."""
    initialize_static_data_section(
        writer,
        static_strings=strings,
        static_variables=variables,
    )


def initialize_static_data_section(
    writer: WriterProtocol,
    static_strings: StringPool,
    static_variables: Mapping[str, Variable[Type]],
) -> None:
    """Initialize data section fields with given values.

    Section is an tuple (label, data)
    Data is an string (raw ASCII) or number (zeroed memory blob)
    """
    write_uninitialized_data_section(writer, static_variables)
    write_initialized_data_section(writer, static_strings, static_variables)
    # Must defined after others - string initializer may forward reference them
    # but we define them by single-pass within writing initializer
    write_text_string_section(writer, static_strings, reference_suffix="d")
