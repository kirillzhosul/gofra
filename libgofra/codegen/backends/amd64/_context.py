from collections.abc import Callable
from dataclasses import dataclass, field
from typing import IO

from libgofra.codegen.abi import AMD64ABI
from libgofra.codegen.backends.string_pool import StringPool
from libgofra.codegen.config import CodegenConfig
from libgofra.codegen.sections._factory import SectionType, get_os_assembler_section
from libgofra.targets.target import Target


@dataclass(frozen=True)
class AMD64CodegenContext:
    """General context for emitting code from IR.

    Probably this is weird and bad way but OK for now.
    @kirillzhosul: Refactor at some point
    """

    config: CodegenConfig

    fd: IO[str]
    on_warning: Callable[[str], None]

    target: Target

    abi: AMD64ABI

    string_pool: StringPool = field(default_factory=StringPool)

    def write(self, *lines: str) -> int:
        return self.fd.write("\t" + "\n\t".join(lines) + "\n")

    def section(self, section: SectionType) -> int:
        return self.fd.write(
            f".section {get_os_assembler_section(section, self.target)}\n",
        )

    def comment_eol(self, line: str) -> int:
        if self.config.no_compiler_comments:
            return 0
        return self.fd.write(f" // {line}\n")
