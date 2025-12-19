from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class MachOSection:
    """Specification of *directive* of section/segment for Mach-O object format."""

    segment: Literal["__TEXT", "__DATA"]
    section: str
    attributes: Sequence[
        Literal[
            # Section types (mutually exclusive - choose ONE):
            "regular",
            "zerofill",
            "cstring_literals",
            # Attributes (only valid with 'regular' type):
            "pure_instructions",
        ]
    ]

    def __post_init__(self) -> None:
        if "zerofill" in self.attributes or "cstring_literals" in self.attributes:
            assert len(self.attributes) == 1
            return

        assert all(
            x in {"regular", "pure_instructions", "strip_static_syms"}
            for x in self.attributes
        ), f"Prohibited attribute sequence for {self.section}"

    def __str__(self) -> str:
        """Get section directive that can be used in assembler section."""
        return ",".join((self.segment, self.section, *self.attributes))


MACHO_SECTION_BSS = MachOSection(
    segment="__DATA",
    section="__bss",
    attributes=("zerofill",),
)  # Uninitialized variables (same as data but different within initialization at runtime by kernel)

MACHO_SECTION_DATA = MachOSection(
    segment="__DATA",
    section="__data",
    attributes=(),
)  # Variables that is read-write and initialized (has initial value)

MACHO_SECTION_STRINGS = MachOSection(
    segment="__TEXT",
    section="__cstring",
    attributes=("cstring_literals",),
)  # Pure C-strings, read-only (string text only)

MACHO_SECTION_INSTRUCTIONS = MachOSection(
    segment="__TEXT",
    section="__text",
    attributes=("regular", "pure_instructions"),
)  # Only instructions here, code goes here
