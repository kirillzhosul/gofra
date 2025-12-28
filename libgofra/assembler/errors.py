from libgofra.assembler.drivers import get_all_drivers
from libgofra.exceptions import GofraError


class NoAssemblerDriverError(GofraError):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

    def __repr__(self) -> str:
        return f"""No assembler driver for target!

Tried to perform assembler step, but no suitable driver (assembler) found!

Possible solutions: Install suitable assembler
Known drivers (may be missing on system): [{", ".join(d().name for d in get_all_drivers())}]

{self.generic_error_name}"""
