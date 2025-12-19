from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class ELFSection:
    """Specification for ELF assembler section directives."""

    name: Literal[".bss", ".data", ".rodata", ".text"]
    type: Literal["@progbits", "@nobits"]
    flags: Sequence[
        Literal[
            "a",  # alloc - occupies memory during execution
            "w",  # write - writable data
            "x",  # execute - executable instructions
            "M",  # merge - can be merged (for strings)
            "S",  # strings - contains null-terminated strings
        ]
    ]

    def __str__(self) -> str:
        """Get ELF section directive for assembler."""
        parts = [self.name]

        parts.append(f'"{"".join(self.flags)}"')

        if self.type:
            parts.append(self.type)

        return ", ".join(parts)


ELF_SECTION_BSS = ELFSection(
    name=".bss",
    flags=("a", "w"),
    type="@nobits",
)  # Uninitialized variables

ELF_SECTION_DATA = ELFSection(
    name=".data",
    flags=("a", "w"),
    type="@progbits",
)  # Initialized read-write data

ELF_SECTION_STRINGS = ELFSection(
    name=".rodata",
    flags=("a", "S", "M"),
    type="@progbits",
)  # Read-only data (strings, constants)

ELF_SECTION_INSTRUCTIONS = ELFSection(
    name=".text",
    flags=("a", "x"),
    type="@progbits",
)  # Executable code
