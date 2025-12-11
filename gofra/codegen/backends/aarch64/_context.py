from collections.abc import MutableMapping
from dataclasses import dataclass, field
from typing import IO

from gofra.codegen.abi import AARCH64ABI


@dataclass(frozen=True)
class AARCH64CodegenContext:
    """General context for emitting code from IR.

    Probably this is weird and bad way but OK for now.
    @kirillzhosul: Refactor at some point
    """

    fd: IO[str]
    strings: MutableMapping[str, str] = field()
    float_constants: MutableMapping[float, str] = field()
    abi: AARCH64ABI

    def write(self, *lines: str) -> int:
        return self.fd.write("\t" + "\n\t".join(lines) + "\n")

    def comment(self, line: str) -> int:
        return self.write(f"// {line}")

    def load_string(self, string: str) -> str:
        string_key = "str%d" % len(self.strings)
        self.strings[string_key] = string
        return string_key
