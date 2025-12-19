from collections.abc import MutableMapping
from dataclasses import dataclass, field
from typing import IO

from libgofra.codegen.abi import AMD64ABI
from libgofra.codegen.sections._factory import SectionType, get_os_assembler_section
from libgofra.targets.target import Target


@dataclass(frozen=True)
class AMD64CodegenContext:
    """General context for emitting code from IR.

    Probably this is weird and bad way but OK for now.
    @kirillzhosul: Refactor at some point
    """

    fd: IO[str]
    strings: MutableMapping[str, str] = field()
    target: Target

    abi: AMD64ABI

    def write(self, *lines: str) -> int:
        return self.fd.write("\t" + "\n\t".join(lines) + "\n")

    def section(self, section: SectionType) -> int:
        return self.fd.write(
            f".section {get_os_assembler_section(section, self.target)}\n",
        )

    def load_string(self, string: str) -> str:
        string_key = "str%d" % len(self.strings)
        self.strings[string_key] = string
        return string_key
