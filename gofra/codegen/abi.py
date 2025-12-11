from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from gofra.codegen.backends.aarch64.registers import AARCH64_GP_REGISTERS
from gofra.codegen.backends.amd64.registers import AMD64_GP_REGISTERS


class ABI[T](Protocol):
    # Register that holds number of system call
    # e.g exit (number is 4 for linux) and this register holds 4
    syscall_number_register: T

    # Same as `arguments_64bit_registers` but for system calls
    # As for System-V AMD64 ABI for example, system call arguments is a bit different
    syscall_arguments_registers: Sequence[T]

    # Return value specification
    # 32/64 bits: if value is less or equals to 32 bits, store that in less significant bytes register
    # primitive/composite: if an return value is structure and it fits in 8-16 bytes, fit bytes above 8 initial bytes into second register (e.g 8B + 8B or 4B + 8B)
    # Indirect pointer: if function returns an structure more than 16 bytes, caller must allocate space on stack and pass that to the called function
    retval_primitive_64bit_register: T
    retval_primitive_32bit_register: T
    retval_composite_64bit_register: T
    retval_composite_32bit_register: T
    retval_indirect_pointer_register: T

    # Registers used to pass arguments
    # all values less than 8 bytes goes into register, if an structure is <16 bytes then it fits into next two available registers
    # if an structure is more than 16 bytes then callee allocates an space and pass an pointer where this structure is located
    arguments_64bit_registers: Sequence[T]


class AMD64ABI(ABI[AMD64_GP_REGISTERS]): ...


class AARCH64ABI(ABI[AARCH64_GP_REGISTERS]): ...


@dataclass(frozen=True, slots=True, init=True)
class DarwinAARCH64ABI(AARCH64ABI):
    """ABI for Darwin (MacOS/iOS e.g) on AARCH64 (ARM64, M-series)."""

    arguments_64bit_registers: Sequence[AARCH64_GP_REGISTERS] = field(
        default_factory=lambda: [
            "X0",
            "X1",
            "X2",
            "X3",
            "X4",
            "X5",
            "X6",
            "X7",
        ],
    )

    syscall_arguments_registers: Sequence[AARCH64_GP_REGISTERS] = field(
        default_factory=lambda: [
            "X0",
            "X1",
            "X2",
            "X3",
            "X4",
            "X5",
            "X6",
            "X7",
        ],
    )

    syscall_number_register = "X16"
    retval_primitive_64bit_register = "X0"
    retval_primitive_32bit_register = "W0"
    retval_composite_64bit_register = "X1"
    retval_composite_32bit_register = "W1"
    retval_indirect_pointer_register = "X0"


@dataclass(frozen=True, slots=True, init=True)
class LinuxAMD64ABI(AMD64ABI):
    """ABI for Linux on AMD64 (x86-64)."""

    arguments_64bit_registers: Sequence[AMD64_GP_REGISTERS] = field(
        default_factory=lambda: [
            "rdi",
            "rsi",
            "rdx",
            "rcx",
            "r8",
            "r9",
        ],
    )

    syscall_arguments_registers: Sequence[AMD64_GP_REGISTERS] = field(
        default_factory=lambda: [
            "rdi",
            "rsi",
            "rdx",
            "r10",
            "r8",
            "r9",
        ],
    )

    syscall_number_register = "rax"
    retval_primitive_64bit_register = "rax"
    retval_primitive_32bit_register = "eax"
    retval_composite_64bit_register = "rdx"
    retval_composite_32bit_register = "edx"
    retval_indirect_pointer_register = "rdi"
