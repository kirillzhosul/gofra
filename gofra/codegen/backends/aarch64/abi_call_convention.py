"""AAPCS64 call convention must work for Apple AAPCS64/System-V AAPCS64."""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal

from gofra.codegen.backends.aarch64._context import AARCH64CodegenContext
from gofra.codegen.backends.aarch64.primitive_instructions import (
    pop_cells_from_stack_into_registers,
    push_register_onto_stack,
    truncate_register_to_32bit_version,
)
from gofra.types._base import Type

if TYPE_CHECKING:
    from gofra.codegen.backends.aarch64.registers import (
        AARCH64_GP_REGISTERS,
    )


def function_abi_call_by_symbol(
    context: AARCH64CodegenContext,
    *,
    name: str,
    parameters: Sequence[Type],
    return_type: Type,
    call_convention: Literal["apple_aapcs64"],
) -> None:
    """Call an function using C ABI (Gofra native and C-FFI both uses C-ABI).

    As Gofra under the hood uses C call convention for functions, this simplifies differences between C and Gofra calls.

    Uses Branch-With-Link (BL) instruction to `jump` into an function and passing Link-Register (LR, x30 on AARCH64) to callee
    Passes arguments before function call with C call convention (e.g via registers and stack depending on arguments byte size and type),
    Restores single return value if requested from retval register.

    Most of the call logic is covered into function own prologue, which unpacks arguments and stores calee stack frame
    """
    # Branch with link to call a subroutine with loading arguments and and acquire retval
    # TODO(@kirillzhosul): Research refactoring with using calling-convention system (e.g for system calls (syscall/cffi/fast-call convention))

    assert call_convention == "apple_aapcs64"
    _load_arguments_for_abi_call_into_registers_from_stack(context, parameters)
    context.write(f"bl {name}")
    _load_return_value_from_abi_registers_into_stack(context, t=return_type)


def load_return_value_from_stack_into_abi_registers(
    context: AARCH64CodegenContext,
    t: Type,
) -> None:
    """Emit code that prepares return value by acquiring it from stack and storing into ABI return value register."""
    if t.is_fp:
        # TODO(@kirillzhosul): Proper return value for floating point types (S0, D0, V0)
        msg = f"FP return value not implemented in codegen ({t})!"
        raise NotImplementedError(msg)

    if t.size_in_bytes <= 0:
        return None  # E.g void, has nothing to return

    abi = context.abi
    if t.size_in_bytes <= 4:
        # Primitive return value as 32 bit (e.g char, bool)
        # directly store into return register (lower 32 bits)
        register = abi.retval_primitive_32bit_register
        return pop_cells_from_stack_into_registers(context, register)

    if t.size_in_bytes <= 8:
        # Primitive return value as 64 bit (e.g default int)
        # directly store into return register (full 64 bits)
        register = abi.retval_primitive_64bit_register
        return pop_cells_from_stack_into_registers(context, register)

    if t.size_in_bytes <= 16:
        # Composite return value up to 128 bits
        # store two segments as registers where lower bytes are in first register (always 64 bit)
        # and remaining bytes in second register
        registers: set[AARCH64_GP_REGISTERS] = {abi.retval_primitive_64bit_register}
        remaining_bytes = t.size_in_bytes - 8
        leftover_reg = (
            abi.retval_composite_32bit_register
            if remaining_bytes <= 4
            else abi.retval_composite_64bit_register
        )
        registers.add(leftover_reg)
        return pop_cells_from_stack_into_registers(context, *registers)

    # TODO(@kirillzhosul): Introduce indirect allocation for return types
    msg = f"Indirect allocation required for return type {t}! Not implemented in AARCH64 codegen!"
    raise NotImplementedError(msg)


def _load_arguments_for_abi_call_into_registers_from_stack(
    context: AARCH64CodegenContext,
    parameters: Sequence[Type],
) -> None:
    """Load arguments from stack into registers to perform an ABI call, if necessary leftover arguments are spilled on stack.

    For example on Darwin ABI with params (x, y, z):
        R0=z (W0/X0)
        R1=y (W1/X1)
        R2=x (W2/X2)
    """
    abi = context.abi
    assert len(parameters) >= 0
    if not parameters:
        return  # Has nothing to pass (e.g empty parameter signature)

    # How much params we can pass by registers
    max_abi_registers = len(abi.arguments_64bit_registers)

    # Wt/Xt registers for non fp/vector arguments
    int_abi_registers = abi.arguments_64bit_registers[: len(parameters)]

    # Reversed pop from stack
    # stack: x y z
    # load in order: z y x (R2, R1, R0)
    # TODO(@kirillzhosul): Possible if we stick with stack approach, define own call-abi to not perform abi call preparation for internal functions (unlike c-ffi)
    registers_to_load: list[AARCH64_GP_REGISTERS] = []
    for register, param_type in zip(
        reversed(int_abi_registers),
        reversed(parameters[:max_abi_registers]),
        strict=True,
    ):
        if param_type.is_fp:
            # TODO(@kirillzhosul): Proper return value for floating point types (S0, D0, V0)
            msg = f"FP argument passing not implemented in codegen ({param_type})!"
            raise NotImplementedError(msg)

        assert param_type.size_in_bytes > 0
        if param_type.size_in_bytes <= 4:
            # 32bit type register (e.g char, bool)
            # truncate to lower register
            registers_to_load.append(truncate_register_to_32bit_version(register))
            continue
        if param_type.size_in_bytes <= 8:
            # Full 64bit register - e.g full int, pointer
            registers_to_load.append(register)
            continue
        if param_type.size_in_bytes <= 16:
            # TODO(@kirillzhosul): Introduce register spill for arguments
            msg = f"Composite param register spill required for param type {param_type}! Not implemented in AARCH64 codegen!"
            raise NotImplementedError(msg)

        # TODO(@kirillzhosul): Introduce indirect allocation for arguments
        msg = f"Indirect allocation required for param type {param_type}! Not implemented in AARCH64 codegen!"
        raise NotImplementedError(msg)

    # Leftover arguments already spilled on stack
    # calee will treat these by itself
    pop_cells_from_stack_into_registers(context, *registers_to_load)


def _load_return_value_from_abi_registers_into_stack(
    context: AARCH64CodegenContext,
    t: Type,
) -> None:
    """Emit code that loads return value by acquiring it from subroutine ABI call registers and spilling onto stack."""
    if t.is_fp:
        # TODO(@kirillzhosul): Proper return value for floating point types (S0, D0, V0)
        msg = f"FP return value not implemented in codegen ({t})!"
        raise NotImplementedError(msg)

    if t.size_in_bytes <= 0:
        return None  # E.g void, has nothing in return

    abi = context.abi
    if t.size_in_bytes <= 4:
        # Primitive return value as 32 bit (e.g char, bool)
        # directly load from return register (lower 32 bits)
        return push_register_onto_stack(context, abi.retval_primitive_32bit_register)

    if t.size_in_bytes <= 8:
        # Primitive return value as 64 bit (e.g default int)
        # directly load from return register (full 64 bits)
        return push_register_onto_stack(context, abi.retval_primitive_64bit_register)
    if t.size_in_bytes <= 16:
        # Composite return value up to 128 bits
        # load two segments as registers where lower bytes are in first register (always 64 bit)
        # and remaining bytes in second register
        push_register_onto_stack(context, abi.retval_primitive_64bit_register)
        remaining_bytes = t.size_in_bytes - 8
        leftover_reg = (
            abi.retval_composite_32bit_register
            if remaining_bytes <= 4
            else abi.retval_composite_64bit_register
        )
        return push_register_onto_stack(context, leftover_reg)

    # TODO(@kirillzhosul): Introduce indirect allocation for return types
    msg = f"Indirect allocation required for return type {t}! Not implemented in AARCH64 codegen!"
    raise NotImplementedError(msg)
