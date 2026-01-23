from __future__ import annotations

from pathlib import Path
from shutil import which
from subprocess import CompletedProcess, run
from typing import TYPE_CHECKING

from libgofra.assembler.drivers._driver_protocol import AssemblerDriverProtocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from libgofra.targets.target import Target


class WabtAssemblerDriver(AssemblerDriverProtocol):
    """Driver for WABT wat2wasm assembler (transpiler)."""

    @property
    def name(self) -> str:
        return "wabt{wat2wasm}"

    @classmethod
    def is_installed(cls) -> bool:
        return cls.find_wat2wasm_tool_path() is not None

    @classmethod
    def find_wat2wasm_tool_path(cls) -> Path | None:
        paths = [which("wat2wasm")]

        for path in paths:
            if not path:
                continue
            return Path(path)

        return None

    @classmethod
    def is_supported(cls, target: Target) -> bool:
        return target.architecture in ("WASM32")

    def assemble(
        self,
        target: Target,
        in_assembly_file: Path,
        out_object_file: Path,
        *,
        debug_information: bool,
        flags: Sequence[str],
    ) -> CompletedProcess[bytes]:
        command = self._compose_assembler_command(
            in_assembly_file=in_assembly_file,
            out_object_file=out_object_file,
            target=target,
            flags=flags,
            debug_information=debug_information,
        )

        return run(
            command,
            check=False,
            capture_output=False,
            timeout=None,
        )

    @classmethod
    def _compose_assembler_command(
        cls,
        target: Target,
        in_assembly_file: Path,
        out_object_file: Path,
        *,
        debug_information: bool,
        flags: Sequence[str],
    ) -> list[str]:
        """Construct wat2wasm command to assemble given assembly file into object file.

        :param target: Compilation target
        :param in_assembly_file: Path to assembly file as input
        :param out_object_file: Path to object file as output
        :param debug_information: If specified, will pass debug info flag to assembler and specify its version
        :param flags: Any additional flags
        """
        _ = target
        executable = cls.find_wat2wasm_tool_path()
        assert executable
        # fmt: off
        command = [
            str(executable),
            str(in_assembly_file),
            *flags, # Additional flags
        ]  
        # fmt: on

        if debug_information:
            command.append("--debug-names")

        # Output into that file
        command.extend(("-o", str(out_object_file)))
        return command
