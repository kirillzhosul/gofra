"""Consts and types related to AARCH64 registers and architecture (including FFI/ABI/IPC)."""

from __future__ import annotations

from typing import Literal

####
# Bare AARCH64 related
####

# Stack is aligment to specified bytes count
# Each cell of an stack must be within that size
# Pushing >2 cells onto stack will lead to cell overflow due to language stack nature.
AARCH64_STACK_ALIGNMENT = 16
AARCH64_STACK_ALINMENT_BIN = 4  # 2 ** 4 -> AARCH64_STACK_ALIGNMENT

# Bits count (size) for different word types
AARCH64_HALF_WORD_BITS = 0xFFFF  # 4 bytes (16 bits)
AARCH64_DOUBLE_WORD_BITS = 0xFFFF_FFFF_FFFF_FFFF  # 16 bytes (64 bits)

# Registers specification for AARCH64
# Skips some of registers (X8-X15, X18-X30) due to currently being unused
type AARCH64_ABI_X_REGISTERS = Literal["X0", "X1", "X2", "X3", "X4", "X5", "X6", "X7"]
type AARCH64_ABI_W_REGISTERS = Literal["W0", "W1", "W2", "W3", "W4", "W5", "W6", "W7"]
type AARCH64_ABI_D_REGISTERS = Literal["D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7"]
type AARCH64_ABI_REGISTERS = (
    AARCH64_ABI_X_REGISTERS | AARCH64_ABI_W_REGISTERS | AARCH64_ABI_D_REGISTERS
)
type AARCH64_IPC_REGISTERS = Literal["X16", "X17"]
type AARCH64_GP_REGISTERS = AARCH64_ABI_REGISTERS | AARCH64_IPC_REGISTERS

STACK_POINTER = "SP"
FRAME_POINTER = "X29"
LINK_REGISTER = "X30"

####
# MacOS related
####


# Epilogue
AARCH64_MACOS_EPILOGUE_EXIT_CODE = 0
AARCH64_MACOS_EPILOGUE_EXIT_SYSCALL_NUMBER = 1
