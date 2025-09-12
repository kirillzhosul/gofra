from collections.abc import MutableMapping
from dataclasses import dataclass, field
from typing import IO


@dataclass(frozen=True)
class AMD64CodegenContext:
    """General context for emitting code from IR.

    Probably this is weird and bad way but OK for now.
    @kirillzhosul: Refactor at some point
    """

    fd: IO[str]
    strings: MutableMapping[str, str] = field()

    def write(self, *lines: str) -> int:
        return self.fd.write("\t" + "\n\t".join(lines) + "\n")

    def load_string(self, string: str) -> str:
        string_key = "str%d" % len(self.strings)
        self.strings[string_key] = string
        return string_key
