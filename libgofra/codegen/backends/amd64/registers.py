"""Consts and types related to AMD64 registers and architecture (including FFI/ABI/IPC)."""

from __future__ import annotations

from typing import Literal

####
# Bare AMD64 related
####

# Stack is alignment to specified bytes count
# Each cell of an stack must be within that size
# Pushing >2 cells onto stack will lead to cell overflow due to language stack nature.
AMD64_STACK_ALIGNMENT = 16
AMD64_STACK_ALIGNMENT_BIN = 4  # 2 ** 4 -> AMD64_STACK_ALIGNMENT

# Registers specification for AMD64
# Skips some of registers due to currently being unused
type AMD64_GP_REGISTERS = Literal[
    "rax",
    "eax",
    "rbx",
    "rdi",
    "edx",
    "rsi",
    "rcx",
    "rdx",
    "r10",
    "r8",
    "r9",
]


####
# Linux related
####

# Epilogue
AMD64_LINUX_EPILOGUE_EXIT_CODE = 0
AMD64_LINUX_EPILOGUE_EXIT_SYSCALL_NUMBER = 60
