from typing import IO, Protocol

from gofra.hir.module import Module
from gofra.targets.target import Target


class CodeGeneratorBackend(Protocol):
    """Base code generator backend protocol.

    All backends inherited from this protocol.
    """

    def __call__(
        self,
        fd: IO[str],
        program: Module,
        target: Target,
    ) -> None: ...
