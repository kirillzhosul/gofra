"""Assembly section specification, writers and etc for different object file formats (ELF/COFF/MACHO)."""

from .bss_variables import write_uninitialized_data_section
from .data_variables import write_initialized_data_section
from .text_strings import write_text_string_section

__all__ = [
    "write_initialized_data_section",
    "write_text_string_section",
    "write_uninitialized_data_section",
]
