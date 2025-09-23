"""Consts and types related to AMD64 registers and architecture (including FFI/ABI/IPC)."""

from __future__ import annotations

from typing import Literal

####
# Bare AMD64 related
####

# Registers specification for AMD64
# Skips some of registers due to currently being unused
type AMD64_GP_REGISTERS = Literal[
    "rax",
    "eax",
    "rbx",
    "rdi",
    "rsi",
    "rcx",
    "rdx",
    "r10",
    "r8",
    "r9",
]


####
# Windows related
####

# Epilogue
AMD64_WINDOWS_ABI_RETVAL_REGISTER: AMD64_GP_REGISTERS = "rax"
AMD64_WINDOWS_ABI_ARGUMENTS_REGISTERS: tuple[AMD64_GP_REGISTERS, ...] = (
    "rcx",
    "rdx",
    "r8",
    "r9",
)
