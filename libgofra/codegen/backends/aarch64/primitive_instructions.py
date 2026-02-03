from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, Literal, cast

from libgofra.hir.operator import OperatorType

from .registers import (
    AARCH64_ABI_W_REGISTERS,
    AARCH64_DOUBLE_WORD_BITS,
    AARCH64_GP_REGISTERS,
    AARCH64_HALF_WORD_BITS,
    AARCH64_STACK_ALIGNMENT,
)

if TYPE_CHECKING:
    from libgofra.codegen.backends.aarch64.writer import WriterProtocol


def drop_stack_slots(
    writer: WriterProtocol,
    *,
    slots_count: int,
    slot_size: int = AARCH64_STACK_ALIGNMENT,
) -> None:
    """Drop stack slots by shifting stack pointer (SP) by N bytes.

    In ARM64 context, a 'stack slot' typically represents an aligned unit
    of memory that can hold primitive values, pointers, or parts of larger objects.
    """
    if slot_size <= 0:
        msg = "`slots_count` must be positive, cannot drop zero or less stack slots"
        raise ValueError(msg)

    shift_in_bits = slot_size * slots_count
    assert shift_in_bits % 2 == 0
    writer.instruction(f"add SP, SP, #{shift_in_bits}")


def pop_cells_from_stack_into_registers(
    writer: WriterProtocol,
    *registers: AARCH64_GP_REGISTERS,
) -> None:
    """Pop cells from stack and store into given registers.

    Each cell is 8 bytes, but stack pointer is always adjusted by `AARCH64_STACK_ALIGNMENT` bytes
    to preserve stack alignment.
    """
    assert registers, "Expected registers to store popped result into!"

    # TODO(@kirillzhosul): LDP for pairs
    for register in registers:
        writer.instruction(
            f"ldr {register}, [SP], #{AARCH64_STACK_ALIGNMENT}",
        )


def push_register_onto_stack(
    writer: WriterProtocol,
    register: AARCH64_GP_REGISTERS,
) -> None:
    """Store given register onto stack under current stack pointer."""
    writer.instruction(f"str {register}, [SP, -{AARCH64_STACK_ALIGNMENT}]!")


def store_integer_into_register(
    writer: WriterProtocol,
    register: AARCH64_GP_REGISTERS,
    value: int,
) -> None:
    """Store given value into given register."""
    writer.instruction(f"mov {register}, #{value}")


def push_float_onto_stack(writer: WriterProtocol, value: float) -> None:
    raise NotImplementedError


def push_integer_onto_stack(
    writer: WriterProtocol,
    value: int,
) -> None:
    """Push given integer onto stack with auto shifting less-significant bytes.

    Value must be less than 16 bytes (18_446_744_073_709_551_615).
    Negative numbers is disallowed.

    TODO(@kirillzhosul): Negative numbers IS disallowed:
        Consider using signed two complement representation with sign bit (highest bit) set
    """
    assert value <= AARCH64_DOUBLE_WORD_BITS, (
        "Tried to push integer that exceeding 16 bytes (64 bits register)."
    )

    is_negative = value < 0
    value = abs(value)

    if value <= AARCH64_HALF_WORD_BITS:
        # We have small immediate value which we may just store without shifts
        writer.instruction(f"mov X0, #{value}")
        if is_negative:
            writer.instruction("neg X0, X0")
        push_register_onto_stack(writer, register="X0")
        return

    preserve_bits = False
    for shift in range(0, 64, 16):
        chunk = hex((value >> shift) & AARCH64_HALF_WORD_BITS)
        if chunk == "0x0":
            # Zeroed chunk so we do not push it as register is zeroed
            continue

        if not preserve_bits:
            # Store upper bits
            writer.instruction(f"movz X0, #{chunk}, lsl #{shift}")
            preserve_bits = True
            continue

        # Store lower bits
        writer.instruction(f"movk X0, #{chunk}, lsl #{shift}")

    if is_negative:
        writer.instruction("sub X0, XZR, X0")

    push_register_onto_stack(writer, register="X0")


def load_memory_from_stack_arguments(writer: WriterProtocol) -> None:
    """Load memory as value using arguments from stack."""
    pop_cells_from_stack_into_registers(writer, "X0")
    writer.instruction("ldr X0, [X0]")
    push_register_onto_stack(writer, "X0")


def store_into_memory_from_stack_arguments(writer: WriterProtocol) -> None:
    """Store value into memory pointer, pointer and value acquired from stack."""
    pop_cells_from_stack_into_registers(writer, "X0", "X1")
    writer.instruction("str X0, [X1]")


def perform_operation_onto_stack(
    writer: WriterProtocol,
    operation: OperatorType,
) -> None:
    """Perform *math* operation onto stack (pop arguments and push back result)."""
    registers = ("X0", "X1")
    if operation == OperatorType.LOGICAL_NOT:
        registers = ("X0",)
    pop_cells_from_stack_into_registers(writer, *registers)

    # TODO(@kirillzhosul): Optimize inc / dec (++, --) when incrementing / decrementing by known values
    match operation:
        case OperatorType.ARITHMETIC_PLUS:
            writer.instruction("add X0, X1, X0")
        case OperatorType.ARITHMETIC_MINUS:
            writer.instruction("sub X0, X1, X0")
        case OperatorType.ARITHMETIC_MULTIPLY:
            writer.instruction("mul X0, X1, X0")
        case OperatorType.ARITHMETIC_DIVIDE:
            writer.instruction("sdiv X0, X1, X0")
        case OperatorType.ARITHMETIC_MODULUS:
            writer.instruction("udiv X2, X1, X0")
            writer.instruction("mul X2, X2, X0")
            writer.instruction("sub X0, X1, X2")
        case OperatorType.LOGICAL_OR | OperatorType.BITWISE_OR:
            # Use bitwise one here even for logical one as we have typechecker which expects boolean types.
            writer.instruction("orr X0, X0, X1")
        case OperatorType.SHIFT_RIGHT:
            writer.instruction("lsr X0, X1, X0")
        case OperatorType.SHIFT_LEFT:
            writer.instruction("lsl X0, X1, X0")
        case OperatorType.BITWISE_AND | OperatorType.LOGICAL_AND:
            # Use bitwise one here even for logical one as we have typechecker which expects boolean types.
            writer.instruction("and X0, X0, X1")
        case OperatorType.LOGICAL_NOT:
            # TODO: Must work only for booleans (0, 1), must be fulfilled with codegen tricks
            writer.instruction("eor X0, X0, 1")
        case OperatorType.BITWISE_XOR:
            writer.instruction("eor X0, X0, X1")
        case (
            OperatorType.COMPARE_EQUALS
            | OperatorType.COMPARE_GREATER
            | OperatorType.COMPARE_GREATER_EQUALS
            | OperatorType.COMPARE_LESS
            | OperatorType.COMPARE_NOT_EQUALS
            | OperatorType.COMPARE_LESS_EQUALS
        ):
            logic_op: dict[
                OperatorType,
                Literal["ne", "ge", "le", "lt", "gt", "eq"],
            ] = {
                OperatorType.COMPARE_NOT_EQUALS: "ne",
                OperatorType.COMPARE_GREATER_EQUALS: "ge",
                OperatorType.COMPARE_LESS_EQUALS: "le",
                OperatorType.COMPARE_LESS: "lt",
                OperatorType.COMPARE_GREATER: "gt",
                OperatorType.COMPARE_EQUALS: "eq",
            }
            compare_registers_boolean(
                writer,
                register_a="X1",
                register_b="X0",
                register="X0",
                condition=logic_op[operation],
            )
        case _:
            msg = f"{operation} cannot be performed by codegen `{perform_operation_onto_stack.__name__}`"
            raise ValueError(msg)
    push_register_onto_stack(writer, "X0")


def evaluate_conditional_block_on_stack_with_jump(
    writer: WriterProtocol,
    jump_over_label: str,
) -> None:
    """Evaluate conditional block by popping current value under SP against zero.

    If condition is false (value on stack) then jump out that conditional block to `jump_over_label`
    """
    pop_cells_from_stack_into_registers(writer, "X0")
    compare_and_jump_to_label(
        writer,
        register="X0",
        label=jump_over_label,
        condition="zero",
    )


def truncate_register_to_32bit_version(
    register: AARCH64_GP_REGISTERS,
) -> AARCH64_ABI_W_REGISTERS:
    """Truncate 64bit version of register into corresponding 32bit version (e.g X0 to W0).

    Accepts only Xt registers (XZR prohibited)
    """
    if register.startswith("X"):
        return cast("AARCH64_ABI_W_REGISTERS", register.replace("X", "W"))

    if register.startswith("W"):
        assert register != "WZR"
        return cast("AARCH64_ABI_W_REGISTERS", register)

    msg = f"Cannot truncate register {register} to corresponding 32bit version!"
    raise NotImplementedError(msg)


###
# Branching related
###


# TODO: `csel` for branchless?


def jump_to_subroutine_from_register(
    writer: WriterProtocol,
    register: AARCH64_GP_REGISTERS,
) -> None:
    """Jump (branch) to indirect subroutine located in given register. Does not do PAC."""
    writer.instruction(f"blr {register}")


def jump_to_subroutine(
    writer: WriterProtocol,
    label: str,
) -> None:
    """Jump (branch) to subroutine with given label. Does not do PAC."""
    assert label
    writer.instruction(f"bl _{label}")


def compare_and_jump_to_label(
    writer: WriterProtocol,
    register: AARCH64_GP_REGISTERS,
    label: str,
    condition: Literal["zero", "nonzero"],
) -> None:
    """Compare that given register is zero and jump to given label if it is."""
    assert label
    if condition == "zero":
        writer.instruction(f"cbz {register}, {label}")
        return

    assert condition == "nonzero"
    writer.instruction(f"cbnz {register}, {label}")
    return


def compare_registers_boolean(
    writer: WriterProtocol,
    register_a: AARCH64_GP_REGISTERS,
    register_b: AARCH64_GP_REGISTERS,
    register: AARCH64_GP_REGISTERS,
    condition: Literal["ne", "ge", "le", "lt", "gt", "eq"],
) -> None:
    writer.instruction(f"cmp {register_a}, {register_b}")
    writer.instruction(f"cset {register}, {condition}")


###
# Memory (instructions, data) related
###


class AddressingMode(Enum):
    """Specifies addressing mode for load label instructions."""

    NEAR = auto()  # `ADR`, low offsets
    PAGE = auto()  # `ADRP` by pages
    EXTERNAL = auto()  # `GOT` runtime


def push_address_of_label_onto_stack(
    writer: WriterProtocol,
    label: str,
    *,
    mode: AddressingMode = AddressingMode.PAGE,
    temp_register: AARCH64_GP_REGISTERS = "X16",
) -> None:
    """Load (form) address of label and store into register with possible page dereferences and push it onto stack.

    :param label: Address of which to get (subroutine, BSS/DATA segment label)
    :param mode: How far label is, specifies how to load label

    """
    get_address_of_label(
        writer,
        destination=temp_register,
        label=label,
        mode=mode,
    )
    push_register_onto_stack(writer, register=temp_register)


def get_address_of_label(
    writer: WriterProtocol,
    destination: AARCH64_GP_REGISTERS,
    label: str,
    *,
    mode: AddressingMode = AddressingMode.PAGE,
) -> None:
    """Load (form) address of label and store into register with possible page dereferences.

    :param label: Address of which to get (subroutine, BSS/DATA segment label)
    :param mode: How far label is, specifies how to load label
    """
    assert label

    match mode:
        case AddressingMode.NEAR:
            # +- 1MB offset
            writer.instruction(f"adr {destination}, {label}")
            return
        case AddressingMode.EXTERNAL:
            # GOT (runtime load)
            writer.instruction(f"adrp {destination}, {label}@GOTPAGE")
            writer.instruction(
                f"ldr {destination}, [{destination}, {label}@GOTPAGEOFF]",
            )
            return
        case AddressingMode.PAGE:
            # +-4GB offset
            writer.instruction(f"adrp {destination}, {label}@PAGE")
            writer.instruction(f"add  {destination}, {destination}, {label}@PAGEOFF")


###
# Software specific
###


def place_software_trap(writer: WriterProtocol, code: int) -> None:
    """Generate a software trap (BRK) instruction."""
    assert 0 < code < 0xFFFF
    writer.instruction(f"brk #{hex(code)}")
