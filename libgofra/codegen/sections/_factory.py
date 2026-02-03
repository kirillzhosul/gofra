from enum import Enum, auto
from typing import Protocol

from libgofra.targets.target import Target

from .elf import (
    ELF_SECTION_BSS,
    ELF_SECTION_DATA,
    ELF_SECTION_INSTRUCTIONS,
    ELF_SECTION_STRINGS,
)
from .macho import (
    MACHO_SECTION_BSS,
    MACHO_SECTION_DATA,
    MACHO_SECTION_DWARF_ABBREV,
    MACHO_SECTION_DWARF_INFO,
    MACHO_SECTION_DWARF_LINES,
    MACHO_SECTION_DWARF_STRINGS,
    MACHO_SECTION_INSTRUCTIONS,
    MACHO_SECTION_STRINGS,
)


class SectionType(Enum):
    BSS = auto()
    DATA = auto()
    STRINGS = auto()
    INSTRUCTIONS = auto()

    DWARF_ABBREV = auto()
    DWARF_LINES = auto()
    DWARF_INFO = auto()
    DWARF_STRINGS = auto()


class Section(Protocol):
    def __str__(self) -> str: ...


def get_os_assembler_section(section: SectionType, target: Target) -> Section:
    match target.operating_system:
        case "Linux":
            return {
                SectionType.BSS: ELF_SECTION_BSS,
                SectionType.DATA: ELF_SECTION_DATA,
                SectionType.INSTRUCTIONS: ELF_SECTION_INSTRUCTIONS,
                SectionType.STRINGS: ELF_SECTION_STRINGS,
            }[section]
        case "Darwin":
            return {
                SectionType.BSS: MACHO_SECTION_BSS,
                SectionType.DATA: MACHO_SECTION_DATA,
                SectionType.INSTRUCTIONS: MACHO_SECTION_INSTRUCTIONS,
                SectionType.STRINGS: MACHO_SECTION_STRINGS,
                SectionType.DWARF_ABBREV: MACHO_SECTION_DWARF_ABBREV,
                SectionType.DWARF_STRINGS: MACHO_SECTION_DWARF_STRINGS,
                SectionType.DWARF_LINES: MACHO_SECTION_DWARF_LINES,
                SectionType.DWARF_INFO: MACHO_SECTION_DWARF_INFO,
            }[section]
        case "None":
            msg = "None operating system means there is no os assembler sections, cannot perform!"
            raise ValueError(msg)
        case "Windows":
            msg = "Windows COFF/PE is not implemented"
            raise NotImplementedError(msg)
