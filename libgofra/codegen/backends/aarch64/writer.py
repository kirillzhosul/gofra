from dataclasses import dataclass
from typing import IO, Literal, Protocol

from libgofra.codegen.config import CodegenConfig
from libgofra.codegen.sections._factory import SectionType, get_os_assembler_section
from libgofra.targets.target import Target


@dataclass
class CISLine:
    type: Literal["instruction", "label", "comment", "section", "directive"]
    text: str
    comment: str | None = None


type SYM_SECT_DIRECTIVES = Literal[
    "zero",
    "byte",
    "short",
    "quad",
    "word",
    "half",
    "ascii",
    "asciz",
    "long",
    "space",
    "fill",
]
type DIRECTIVES = (
    SYM_SECT_DIRECTIVES
    | Literal[
        "p2align",
        "align",
        "globl",
        "file",
        "loc",
        "cfi_startproc",
        "cfi_endproc",
        "cfi_def_cfa_offset",
        "cfi_def_cfa",
        "cfi_offset",
        "set",
        "cfi_def_cfa_register",
        "subsections_via_symbols",
    ]
)


class WriterProtocol(Protocol):
    config: CodegenConfig

    def section(self, section: SectionType) -> None: ...
    def comment(self, line: str) -> None: ...
    def comment_eol(self, line: str) -> None: ...
    def label(self, label: str) -> None: ...

    def directive(
        self,
        directive: DIRECTIVES,
        *args: str | int,
    ) -> None: ...

    def instruction(self, instruction: str) -> None: ...

    def sym_sect_directive(
        self,
        directive: SYM_SECT_DIRECTIVES,
        *args: str | int,
        comment: str | None = None,
    ) -> None: ...

    def dwarf_loc_directive(self, n: int, line: int, col: int) -> None:
        return self.directive("loc", " ".join(map(str, [n, line, col])))


class AARCH64BufferedWriterImplementation(WriterProtocol):
    buffer: list[CISLine]
    config: CodegenConfig

    target: Target

    def __init__(
        self,
        fd: IO[str],
        config: CodegenConfig,
        target: Target,
    ) -> None:
        self.fd = fd
        self.target = target
        self.buffer = []
        self.config = config

    def section(self, section: SectionType) -> None:
        self.buffer.append(
            CISLine(
                type="section",
                text=f".section {get_os_assembler_section(section, self.target)}",
            ),
        )

    def comment(self, line: str) -> None:
        if self.config.no_compiler_comments:
            return
        assert self.buffer[-1].comment is None
        self.buffer[-1].comment = line

    def comment_eol(self, line: str) -> None:
        if self.config.no_compiler_comments:
            return
        self.buffer.append(CISLine(type="comment", text=f"// {line}"))

    def label(self, label: str) -> None:
        """Emit label to code."""
        self.buffer.append(CISLine(type="label", text=f"{label}:"))

    def directive(
        self,
        directive: DIRECTIVES,
        *args: str | int,
        comment: str | None = None,
    ) -> None:
        text = " ".join([f".{directive}", ", ".join(map(str, args))])
        self.buffer.append(CISLine(type="directive", text=text, comment=comment))

    def instruction(self, instruction: str) -> None:
        self.buffer.append(CISLine(type="instruction", text=instruction))

    def sym_sect_directive(
        self,
        directive: SYM_SECT_DIRECTIVES,
        *args: str | int,
        comment: str | None = None,
    ) -> None:
        self.directive(directive, *args, comment=comment)

    def full_buffer_flush(self) -> None:
        for cis_line in self.buffer:
            self.fd.write(cis_line.text)
            if cis_line.comment:
                self.fd.write(f" ; {cis_line.comment}")
            self.fd.write("\n")


class AARCH64ImmediateWriterImplementation(WriterProtocol):
    _fd: IO[str]
    buffer: list[str]
    config: CodegenConfig

    target: Target

    def __init__(
        self,
        fd: IO[str],
        config: CodegenConfig,
        target: Target,
    ) -> None:
        self._fd = fd
        self.target = target
        self.config = config

    def section(self, section: SectionType) -> None:
        self._fd.write(
            f".section {get_os_assembler_section(section, self.target)}\n",
        )

    def _write(self, line: str) -> None:
        self._fd.write(line)

    def comment(self, line: str) -> None:
        if self.config.no_compiler_comments:
            return
        self._fd.write(f"// {line}\n")

    def comment_eol(self, line: str) -> None:
        if self.config.no_compiler_comments:
            return
        self._fd.write(f" // {line}\n")

    def label(self, label: str) -> None:
        self._fd.write(f"{label}:\n")

    def directive(
        self,
        directive: DIRECTIVES,
        *args: str | int,
        comment: str | None = None,
    ) -> None:
        self._fd.write(" ".join([f".{directive}", ", ".join(map(str, args))]))
        if comment:
            self._fd.write(f" ; {comment}")
        self._fd.write("\n")

    def instruction(self, instruction: str) -> None:
        self._fd.write(instruction)
        self._fd.write("\n")

    def sym_sect_directive(
        self,
        directive: SYM_SECT_DIRECTIVES,
        *args: str | int,
        comment: str | None = None,
    ) -> None:
        self._fd.write("\t")
        self.directive(directive, *args, comment=comment)
