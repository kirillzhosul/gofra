from collections.abc import MutableMapping
from dataclasses import dataclass, field
from typing import IO

from gofra.typecheck.types import GofraType

from .abi import DarwinAARCH64ABI


@dataclass(frozen=True)
class AARCH64CodegenContext:
    """General context for emitting code from IR.

    Probably this is weird and bad way but OK for now.
    @kirillzhosul: Refactor at some point
    """

    fd: IO[str]
    strings: MutableMapping[str, str] = field()
    abi = DarwinAARCH64ABI

    def write(self, *lines: str) -> int:
        return self.fd.write("\t" + "\n\t".join(lines) + "\n")

    def comment(self, line: str) -> int:
        return self.write(f"// {line}")

    def load_string(self, string: str) -> str:
        string_key = "str%d" % len(self.strings)
        self.strings[string_key] = string
        return string_key


GOFRA_TYPE_WORD_SIZE = {
    GofraType.ANY: 0,
    GofraType.VOID: 0,
    GofraType.BOOLEAN: 8,
    GofraType.INTEGER: 8,
    GofraType.POINTER: 8,
}
