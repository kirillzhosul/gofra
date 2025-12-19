"""Assembly section specification for different object file formats (ELF/COFF/MACHO)."""

from ._factory import SectionType, get_os_assembler_section

__all__ = ["SectionType", "get_os_assembler_section"]
