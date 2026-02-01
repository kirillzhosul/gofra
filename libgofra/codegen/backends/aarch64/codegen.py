"""Core AARCH64 MacOS codegen."""

from __future__ import annotations

from typing import IO, TYPE_CHECKING, Literal

from libgofra.codegen.abi import DarwinAARCH64ABI
from libgofra.codegen.backends.aarch64.executable_entry_point import (
    aarch64_program_entry_point,
)
from libgofra.codegen.backends.aarch64.instruction_set import aarch64_instruction_set
from libgofra.codegen.backends.aarch64.static_data_section import (
    aarch64_data_section,
)
from libgofra.codegen.backends.aarch64.subroutines import (
    function_begin_with_prologue,
    function_end_with_epilogue,
)
from libgofra.codegen.backends.frame import is_native_function_has_frame
from libgofra.codegen.backends.string_pool import StringPool
from libgofra.codegen.sections import SectionType
from libgofra.codegen.sections._factory import get_os_assembler_section

if TYPE_CHECKING:
    from collections.abc import Callable

    from libgofra.codegen.abi import AARCH64ABI
    from libgofra.codegen.config import CodegenConfig
    from libgofra.hir.function import Function
    from libgofra.hir.module import Module
    from libgofra.targets.target import Target


class AARCH64CodegenBackend:
    target: Target
    module: Module

    on_warning: Callable[[str], None]
    config: CodegenConfig

    _fd: IO[str]
    abi: AARCH64ABI
    target: Target

    string_pool: StringPool

    def __init__(
        self,
        target: Target,
        module: Module,
        fd: IO[str],
        on_warning: Callable[[str], None],
        config: CodegenConfig,
    ) -> None:
        self.target = target
        self.module = module
        self.on_warning = on_warning
        self._fd = fd
        self.config = config

        self.abi = DarwinAARCH64ABI()
        self.string_pool = StringPool()
        self.strings = {}

    def emit(self) -> None:
        """AARCH64 code generation backend."""
        # Executable section with instructions only (pure_instructions)
        self.section(SectionType.INSTRUCTIONS)

        for function in self.module.executable_functions:
            function_define_with_instruction_set(self, self.module, function)

        if self.module.entry_point_ref:
            aarch64_program_entry_point(
                self,
                system_entry_point_name=self.config.system_entry_point_name,
                entry_point=self.module.entry_point_ref,
                target=self.target,
            )
        aarch64_data_section(self, self.module)

    def _write(self, *lines: str) -> int:
        return self._fd.write("\t" + "\n\t".join(lines) + "\n")

    def section(self, section: SectionType) -> int:
        return self._fd.write(
            f".section {get_os_assembler_section(section, self.target)}\n",
        )

    def comment(self, line: str) -> int:
        if self.config.no_compiler_comments:
            return 0
        return self._write(f"// {line}")

    def comment_eol(self, line: str) -> int:
        if self.config.no_compiler_comments:
            return 0
        return self._fd.write(f" // {line}\n")

    def label(self, label: str) -> None:
        """Emit label to code."""
        self._fd.write(f"{label}:\n")

    def directive(
        self,
        directive: Literal[
            "p2align",
            "align",
            "globl",
            "zero",
            "byte",
            "quad",
            "word",
            "half",
            "asciz",
            "space",
            "fill",
            "cfi_startproc",
            "cfi_endproc",
            "cfi_def_cfa_offset",
            "cfi_def_cfa",
            "cfi_offset",
            "cfi_def_cfa_register",
        ],
        *args: str | int,
    ) -> None:
        self._fd.write(" ".join([f".{directive}", ", ".join(map(str, args))]))
        self._fd.write("\n")

    def instruction(self, instruction: str) -> None:
        self._write(instruction)

    def sym_sect_directive(
        self,
        directive: Literal[
            "zero",
            "byte",
            "quad",
            "word",
            "half",
            "asciz",
            "space",
            "fill",
        ],
        *args: str | int,
    ) -> None:
        self._fd.write("\t")
        self.directive(directive, *args)


def function_define_with_instruction_set(
    context: AARCH64CodegenBackend,
    program: Module,
    function: Function,
) -> None:
    """Define all executable functions inside final executable with their executable body respectfully.

    Provides an prolog and epilogue.
    """
    has_frame = is_native_function_has_frame(context.config, function)

    function_begin_with_prologue(
        context,
        name=function.name,
        local_variables=function.variables,
        global_name=function.name if function.is_public else None,
        preserve_frame=has_frame,
        parameters=function.parameters,
    )

    aarch64_instruction_set(context, function.operators, program, function)

    # TODO(@kirillzhosul): This is included even after explicit return after end
    if not function.is_naked:
        function_end_with_epilogue(
            context,
            has_preserved_frame=has_frame,
            return_type=function.return_type,
            is_early_return=False,
        )
