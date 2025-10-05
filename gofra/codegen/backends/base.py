from typing import IO, Protocol

from gofra.context import ProgramContext
from gofra.targets.target import Target


class CodeGeneratorBackend(Protocol):
    """Base code generator backend protocol.

    All backends inherited from this protocol.
    """

    def __call__(
        self,
        fd: IO[str],
        program: ProgramContext,
        target: Target,
    ) -> None: ...
