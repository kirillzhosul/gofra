from libgofra.assembler.drivers._get_assembler_driver import get_supported_drivers
from libgofra.exceptions import GofraError
from libgofra.targets.target import Target


class NoAssemblerDriverError(GofraError):
    def __init__(self, target: Target) -> None:
        self.target = target

    def __repr__(self) -> str:
        return f"""No assembler driver for target!

Tried to perform assembler step, but no suitable driver (assembler) found for target {self.target.triplet}!

Possible solutions: Install suitable assembler
Supported drivers for targets (may be missing on system): [{", ".join(d().name for d in get_supported_drivers(self.target))}]

{self.generic_error_name}"""
