from collections.abc import Callable
from typing import IO, Protocol

from libgofra.hir.module import Module
from libgofra.targets.target import Target


class CodeGeneratorBackend(Protocol):
    """Base code generator backend protocol.

    All backends inherited from this protocol.
    """

    def __init__(
        self,
        target: Target,
        module: Module,
        fd: IO[str],
        on_warning: Callable[[str], None],
        *,
        emit_dwarf_cfi: bool,
    ) -> None: ...

    def emit(self) -> None: ...
