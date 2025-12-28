from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path
from subprocess import CompletedProcess

from libgofra.targets.target import Target


class AssemblerDriverProtocol(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def assemble(
        self,
        target: Target,
        in_assembly_file: Path,
        out_object_file: Path,
        *,
        debug_information: bool,
        flags: Sequence[str],
    ) -> CompletedProcess[bytes]:
        """Call assembler as an process to assemble given assembly file into object file.

        :param target: Compilation target
        :param in_assembly_file: Path to assembly file as input
        :param out_object_file: Path to object file as output
        :param debug_information: If specified, will pass debug info flag to assembler and specify its version
        :param flags: Any additional flags
        """
        ...

    @classmethod
    @abstractmethod
    def is_supported(cls, target: Target) -> bool:
        """Is given target supported by that assembler driver?."""
        ...

    @classmethod
    @abstractmethod
    def is_installed(cls) -> bool:
        """Is given assembler driver installed on system?."""
        ...
