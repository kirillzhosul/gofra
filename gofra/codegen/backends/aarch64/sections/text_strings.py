from __future__ import annotations

from typing import TYPE_CHECKING

from gofra.codegen.sections._factory import SectionType

if TYPE_CHECKING:
    from collections.abc import Mapping

    from gofra.codegen.backends.aarch64._context import AARCH64CodegenContext


def write_text_string_section(
    context: AARCH64CodegenContext,
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
        context.fd.write(f'{name}{reference_suffix}: .asciz "{data}"\n')
