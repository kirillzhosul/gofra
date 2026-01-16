from __future__ import annotations

from typing import TYPE_CHECKING

from libgofra.codegen.sections._factory import SectionType

if TYPE_CHECKING:
    from collections.abc import Mapping

    from libgofra.codegen.backends.aarch64._context import AARCH64CodegenContext
    from libgofra.hir.variable import Variable
    from libgofra.types._base import Type


def write_uninitialized_data_section(
    context: AARCH64CodegenContext,
    variables: Mapping[str, Variable[Type]],
) -> None:
    """Emit data section with uninitialized variables."""
    uninitialized_variables = {
        k: v for k, v in variables.items() if v.initial_value is None
    }

    if not uninitialized_variables:
        return

    context.section(SectionType.BSS)
    aligned_by: int | None = None
    for name, variable in uninitialized_variables.items():
        type_size = variable.size_in_bytes
        assert type_size, (
            f"Variable has type with zero size ({name} defined at {variable.defined_at})"
        )

        alignment = variable.type.alignment
        if alignment != aligned_by:
            context.fd.write(f".align {alignment}\n")
            aligned_by = alignment

        context.fd.write(f"{name}: .space {type_size}\n")
