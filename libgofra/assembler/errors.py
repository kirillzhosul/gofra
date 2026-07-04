from libgofra.assembler.drivers._driver_protocol import AssemblerDriverProtocol
from libgofra.exceptions import GofraError
from libgofra.targets.target import Target


class NoAssemblerDriverError(GofraError):
    def __init__(
        self,
        target: Target,
        supported_drivers: list[type[AssemblerDriverProtocol]],
    ) -> None:
        self.target = target
        self.supported_drivers = supported_drivers

    def __repr__(self) -> str:
        return f"""No assembler driver for target!

Tried to perform assembler step, but no suitable driver (assembler) found for target {self.target.triplet}!

Possible solutions: Install suitable assembler
Supported drivers for targets (may be missing on system): [{", ".join(d().name for d in self.supported_drivers)}]

{self.generic_error_name}"""


class ClangDoesNotSupportWasmError(GofraError):
    def __init__(self, target: Target) -> None:
        self.target = target

    def __repr__(self) -> str:
        return f"""Clang driver does not support WebAssembly target!

Tried to perform assembler for target {self.target.triplet}!

Clang does not support WebAssembly target, please use another assembler driver (e.g. wabt) for this target.

{self.generic_error_name}"""
