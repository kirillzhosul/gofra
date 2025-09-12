"""Assembly abstraction layer that hides declarative assembly OPs into functions that generates that for you."""

from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from .registers import (
    AMD64_WINDOWS_ABI_ARGUMENTS_REGISTERS,
    AMD64_WINDOWS_ABI_RETVAL_REGISTER,
)

if TYPE_CHECKING:
    from gofra.codegen.backends.general import CODEGEN_GOFRA_ON_STACK_OPERATIONS

    from ._context import AMD64CodegenContext
    from .registers import AMD64_GP_REGISTERS


def drop_cells_from_stack(context: AMD64CodegenContext, *, cells_count: int) -> None:
    """Drop stack cells from stack.

    Stack alignment should be review, but `popq` unlike `pop` will shift by 64 bits
    """
    assert cells_count > 0, "Tried to drop negative cells count from stack"
    for _ in range(cells_count):
        context.write("pop rax")  # Use zero regiseter?


def pop_cells_from_stack_into_registers(
    context: AMD64CodegenContext,
    *registers: AMD64_GP_REGISTERS,
) -> None:
    """Pop cells from stack and store into given registers.

    Stack alignment should be review, but probably this codegen ensure with `popq`/`pushq` that all cells are 64 bits
    """
    assert registers, "Expected registers to store popped result into!"

    for register in registers:
        context.write(f"pop {register}")


def push_register_onto_stack(
    context: AMD64CodegenContext,
    register: AMD64_GP_REGISTERS,
) -> None:
    """Store given register onto stack under current stack pointer."""
    context.write(f"push {register}")


def store_integer_into_register(
    context: AMD64CodegenContext,
    register: AMD64_GP_REGISTERS,
    value: int,
) -> None:
    """Store given value into given register (as QWORD)."""
    context.write(f"mov {register}, {value}")


def push_integer_onto_stack(
    context: AMD64CodegenContext,
    value: int,
) -> None:
    """Push given integer onto stack.

    Negative numbers is dissalowed.

    TODO(@kirillzhosul, @stepanzubkov): Negative numbers IS dissalowed
    TODO(@kirillzhosul, @stepanzubkov): Review max and etc like in AARCH64_MacOS
    """
    assert value >= 0, "Tried to push negative integer onto stack!"

    store_integer_into_register(context, register="rax", value=value)
    push_register_onto_stack(context, register="rax")


def push_static_address_onto_stack(
    context: AMD64CodegenContext,
    segment: str,
) -> None:
    """Push executable static memory addresss onto stack with page dereference."""
    context.write(f"lea rax, [rel {segment}]")
    push_register_onto_stack(context, register="rax")


def initialize_static_data_section(
    context: AMD64CodegenContext,
    static_data_section: list[tuple[str, str | int]],
) -> None:
    """Initialize data section fields with given values.

    Section is an tuple (label, data)
    Data is an string (raw ASCII) or number (zeroed memory blob)
    TODO(@kirillzhosul, @stepanzubkov): Review alignment for data sections.
    """
    context.fd.write("section .data\n")
    for name, data in static_data_section:
        if isinstance(data, str):
            context.fd.write(f'{name}: db "{data}", 0\n')
            continue
    context.fd.write("section .bss\n")
    for name, data in static_data_section:
        if not isinstance(data, str):
            context.fd.write(f"{name}: resb {data}\n")
            continue


def function_end_with_epilogue(context: AMD64CodegenContext) -> None:
    """Functions epilogue at the end. Restores required fields (like stack-pointer)."""
    context.write("ret")


def function_begin_with_prologue(
    context: AMD64CodegenContext,
    *,
    function_name: str,
    as_global_linker_symbol: bool,
) -> None:
    """Begin an function symbol with prologue with preparing required (like stack-pointer).

    TODO(@kirillzhosul, @stepanzubkov): Review alignment for executable sections.
    """
    if as_global_linker_symbol:
        context.fd.write(f"global {function_name}\n")
    context.fd.write(f"{function_name}:\n")


def call_function_block(
    context: AMD64CodegenContext,
    function_name: str,
    *,
    abi_ffi_push_retval_onto_stack: bool,
    abi_ffi_arguments_count: int,
) -> None:
    """Call an function with preparing required fields (like stack-pointer).

    Also allows to call ABI/FFI function with providing arguments and return value (retval) via:
    `abi_ffi_push_retval_onto_stack` / `abi_ffi_arguments_count`
    """
    assert abi_ffi_arguments_count >= 0, "FFI arguments count cannot go negative"
    if abi_ffi_arguments_count:
        arguments = abi_ffi_arguments_count
        registers = AMD64_WINDOWS_ABI_ARGUMENTS_REGISTERS[:arguments][::-1]
        pop_cells_from_stack_into_registers(context, *registers)

    context.write(f"call {function_name}")

    if abi_ffi_push_retval_onto_stack:
        push_register_onto_stack(context, AMD64_WINDOWS_ABI_RETVAL_REGISTER)


def store_into_memory_from_stack_arguments(context: AMD64CodegenContext) -> None:
    """Store value from into memory pointer, pointer and value acquired from stack."""
    pop_cells_from_stack_into_registers(context, "rax", "rbx")
    context.write("mov rbx, rax")


def load_memory_from_stack_arguments(context: AMD64CodegenContext) -> None:
    """Load memory as value using arguments from stack."""
    pop_cells_from_stack_into_registers(context, "rax")
    context.write("mov rax, rax")
    push_register_onto_stack(context, "rax")


def perform_operation_onto_stack(
    context: AMD64CodegenContext,
    operation: CODEGEN_GOFRA_ON_STACK_OPERATIONS,
) -> None:
    """Perform *math* operation onto stack (pop arguments and push back result)."""
    is_unary = operation in ("++", "--")
    registers = ("rax",) if is_unary else ("rax", "rbx")
    pop_cells_from_stack_into_registers(context, *registers)

    match operation:
        case "+":
            context.write("add rax, rbx")
        case "-":
            context.write("sub rax, rbx")
        case "*":
            context.write("mul rax, rbx")
        case "//":
            context.write(
                "xor rdx, rdx",
                "div rbx",
            )
        case "%":
            context.write(
                "xor rdx, rdx",
                "div rbx",
                "mov rax, rdx",
            )
        case "++":
            context.write("inc rax")
        case "--":
            context.write("dec rax")
        case "!=" | ">=" | "<=" | "<" | ">" | "==":
            logic_op = {
                "!=": "ne",
                ">=": "ge",
                "<=": "le",
                "<": "l",
                ">": "g",
                "==": "e",
            }

            context.write(
                "cmp rax, rbx",
                "mov rax, 0",  # Clear rax
                f"set{logic_op[operation]} al",  # Set low byte
                "and rax, 1",  # Ensure only 0 or 1
            )
        case _:
            assert_never()
    push_register_onto_stack(context, "rax")


def evaluate_conditional_block_on_stack_with_jump(
    context: AMD64CodegenContext,
    jump_over_label: str,
) -> None:
    """Evaluate conditional block by popping current value under SP againts zero.

    If condition is false (value on stack) then jump out that conditional block to `jump_over_label`
    """
    pop_cells_from_stack_into_registers(context, "rax")
    context.write(
        "cmp rax, 0",
        f"je {jump_over_label}",
    )
