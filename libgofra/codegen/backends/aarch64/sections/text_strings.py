from __future__ import annotations

from typing import TYPE_CHECKING

from libgofra.codegen.sections._factory import SectionType

if TYPE_CHECKING:
    from collections.abc import Mapping

    from libgofra.codegen.backends.aarch64.codegen import AARCH64CodegenBackend


def write_text_string_section(
    context: AARCH64CodegenBackend,
    strings: Mapping[str, str],
    *,
    reference_suffix: str,
) -> None:
    """Emit text section with pure string text.

    :param reference_suffix: Append to each string symbol as it may overlap with real structure of string.
    """
    if not strings:
        return
    context.section(SectionType.STRINGS)
    for name, data in strings.items():
        context.label(f"{name}{reference_suffix}")
        context.sym_sect_directive("asciz", f'"{data}"')
