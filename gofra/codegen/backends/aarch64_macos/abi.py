from dataclasses import dataclass

from gofra.targets.target import Target

from .registers import AARCH64_ABI_REGISTERS, AARCH64_IPC_REGISTERS


@dataclass(frozen=True)
class AARCH64ABI:
    syscall_number_register: AARCH64_IPC_REGISTERS
    return_value_register: AARCH64_ABI_REGISTERS
    argument_registers: tuple[AARCH64_ABI_REGISTERS, ...]


type ABI = AARCH64ABI
DarwinAARCH64ABI = AARCH64ABI(
    syscall_number_register="X16",
    return_value_register="X0",
    argument_registers=(
        "X0",
        "X1",
        "X2",
        "X3",
        "X4",
        "X5",
        "X6",
        "X7",
    ),
)


def get_abi_from_target(target: Target) -> ABI:
    if target.architecture != "ARM64" or target.operating_system != "Darwin":
        raise NotImplementedError

    return DarwinAARCH64ABI
