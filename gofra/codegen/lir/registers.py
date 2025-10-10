from dataclasses import dataclass


class LIRVirtualRegisterAllocator:
    unused_machine_registers: list[str]

    def __init__(self, virtual_temp_machine_registers: list[str]) -> None:
        self.virtual_temp_machine_registers = virtual_temp_machine_registers
        self.unused_machine_registers = []
        self.reset_virtual_space()

    def reset_virtual_space(self) -> None:
        self.unused_machine_registers = self.virtual_temp_machine_registers.copy()[::-1]

    def next_free_machine_register(self) -> str:
        if len(self.unused_machine_registers) == 0:
            msg = f"Tried to get next free machine register but got out-of-registers. Unused Regs: {self.unused_machine_registers}, while space is: {self.virtual_temp_machine_registers}"
            raise ValueError(msg)
        return self.unused_machine_registers.pop()


class LIRVirtualRegister:
    def __init__(self, allocator: LIRVirtualRegisterAllocator) -> None:
        self.name = allocator.next_free_machine_register()

    def __repr__(self) -> str:
        return f"V-Reg [{self.name}]"


class LIRMachineRegister(LIRVirtualRegister):
    def __init__(self, name: str) -> None:
        self.name = name


@dataclass
class LIRImmediate:
    # TODO(@kirillzhosul): Unused RN
    value: int

    def __repr__(self) -> str:
        return f"Immediate (={self.value}"
