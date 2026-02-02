"""Core AARCH64 MacOS codegen."""

from __future__ import annotations

from typing import IO, TYPE_CHECKING

from libgofra.codegen.abi import DarwinAARCH64ABI
from libgofra.codegen.backends.aarch64.executable_entry_point import (
    aarch64_program_entry_point,
)
from libgofra.codegen.backends.aarch64.instruction_set import aarch64_instruction_set
from libgofra.codegen.backends.aarch64.peephole_isa_optimizer import (
    peephole_isa_optimizer_pass,
)
from libgofra.codegen.backends.aarch64.static_data_section import (
    aarch64_data_section,
)
from libgofra.codegen.backends.aarch64.subroutines import (
    function_begin_with_prologue,
    function_end_with_epilogue,
)
from libgofra.codegen.backends.aarch64.writer import (
    AARCH64BufferedWriterImplementation,
    AARCH64ImmediateWriterImplementation,
    WriterProtocol,
)
from libgofra.codegen.backends.frame import is_native_function_has_frame
from libgofra.codegen.backends.string_pool import StringPool
from libgofra.codegen.sections import SectionType

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

    config: CodegenConfig

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
        _ = on_warning
        self.target = target
        self.module = module

        self.config = config

        if config.peephole_isa_optimizer:
            self.writer = AARCH64BufferedWriterImplementation(fd, config, target)
        else:
            self.writer = AARCH64ImmediateWriterImplementation(fd, config, target)

        self.abi = DarwinAARCH64ABI()
        self.string_pool = StringPool()

    def emit(self) -> None:
        """AARCH64 code generation backend."""
        # Executable section with instructions only (pure_instructions)
        self.writer.section(SectionType.INSTRUCTIONS)

        for function in self.module.executable_functions:
            function_define_with_instruction_set(
                self.writer,
                self.abi,
                self.string_pool,
                self.module,
                function,
            )

        if self.module.entry_point_ref:
            aarch64_program_entry_point(
                self.writer,
                self.abi,
                system_entry_point_name=self.config.system_entry_point_name,
                entry_point=self.module.entry_point_ref,
                target=self.target,
            )
        aarch64_data_section(self.writer, self.string_pool, self.module.variables)

        if self.config.peephole_isa_optimizer:
            assert isinstance(self.writer, AARCH64BufferedWriterImplementation)
            peephole_isa_optimizer_pass(self.writer)
            self.writer.full_buffer_flush()


def function_define_with_instruction_set(
    writer: WriterProtocol,
    abi: AARCH64ABI,
    string_pool: StringPool,
    module: Module,
    function: Function,
) -> None:
    """Define all executable functions inside final executable with their executable body respectfully.

    Provides an prolog and epilogue.
    """
    has_frame = is_native_function_has_frame(writer.config, function)

    function_begin_with_prologue(
        writer,
        abi,
        string_pool,
        name=function.name,
        local_variables=function.variables,
        global_name=function.name if function.is_public else None,
        preserve_frame=has_frame,
        parameters=function.parameters,
    )

    aarch64_instruction_set(
        writer,
        abi,
        string_pool,
        function.operators,
        module,
        function,
    )

    # TODO(@kirillzhosul): This is included even after explicit return after end
    if not function.is_naked:
        function_end_with_epilogue(
            writer,
            abi,
            has_preserved_frame=has_frame,
            return_type=function.return_type,
            is_early_return=False,
        )
