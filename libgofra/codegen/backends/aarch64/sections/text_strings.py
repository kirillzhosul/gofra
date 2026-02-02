from __future__ import annotations

from typing import TYPE_CHECKING

from libgofra.codegen.sections._factory import SectionType

if TYPE_CHECKING:
    from libgofra.codegen.backends.aarch64.writer import WriterProtocol
    from libgofra.codegen.backends.string_pool import StringPool


def write_text_string_section(
    writer: WriterProtocol,
    strings: StringPool,
    *,
    reference_suffix: str,
) -> None:
    """Emit text section with pure string text.

    :param reference_suffix: Append to each string symbol as it may overlap with real structure of string.
    """
    if strings.is_empty():
        return
    writer.section(SectionType.STRINGS)
    for data, name in strings.get_view():
        writer.label(f"{name}{reference_suffix}")
        writer.sym_sect_directive("asciz", f'"{data}"')
