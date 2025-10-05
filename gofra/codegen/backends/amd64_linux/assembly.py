"""Assembly abstraction layer that hides declarative assembly OPs into functions that generates that for you."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, assert_never

from gofra.types._base import Type
from gofra.types.primitive.void import VoidType

from .registers import (
    AMD64_LINUX_ABI_ARGUMENTS_REGISTERS,
    AMD64_LINUX_ABI_RETVAL_REGISTER,
    AMD64_LINUX_SYSCALL_ARGUMENTS_REGISTERS,
    AMD64_LINUX_SYSCALL_NUMBER_REGISTER,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from gofra.codegen.backends.general import CODEGEN_GOFRA_ON_STACK_OPERATIONS
    from gofra.parser.variables import Variable

    from ._context import AMD64CodegenContext
    from .registers import AMD64_GP_REGISTERS


def drop_cells_from_stack(context: AMD64CodegenContext, *, cells_count: int) -> None:
    """Drop stack cells from stack.

    Stack alignment should be review, but `popq` unlike `pop` will shift by 64 bits
    """
    assert cells_count > 0, "Tried to drop negative cells count from stack"
    for _ in range(cells_count):
        context.write("popq rax")  # Use zero regiseter?


def pop_cells_from_stack_into_registers(
    context: AMD64CodegenContext,
    *registers: AMD64_GP_REGISTERS,
) -> None:
    """Pop cells from stack and store into given registers.

    Stack alignment should be review, but probably this codegen ensure with `popq`/`pushq` that all cells are 64 bits
    """
    assert registers, "Expected registers to store popped result into!"

    for register in registers:
        context.write(f"popq {register}")


def push_register_onto_stack(
    context: AMD64CodegenContext,
    register: AMD64_GP_REGISTERS,
) -> None:
    """Store given register onto stack under current stack pointer."""
    context.write(f"pushq {register}")


def store_integer_into_register(
    context: AMD64CodegenContext,
    register: AMD64_GP_REGISTERS,
    value: int,
) -> None:
    """Store given value into given register (as QWORD)."""
    context.write(f"movq ${value}, {register}")


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
    context.write(f"leaq {segment}(rip), rax")
    push_register_onto_stack(context, register="rax")


def initialize_static_data_section(
    context: AMD64CodegenContext,
    static_strings: Mapping[str, str],
    static_variables: Mapping[str, Variable],
) -> None:
    """Initialize data section fields with given values.

    Section is an tuple (label, data)
    Data is an string (raw ASCII) or number (zeroed memory blob)
    TODO(@kirillzhosul, @stepanzubkov): Review alignment for data sections.
    """
    context.fd.write(".section .data\n")

    for name, data in static_strings.items():
        context.fd.write(f'{name}: .asciz "{data}"\n')
    for name, variable in static_variables.items():
        typesize = variable.type.size_in_bytes
        if typesize != 0:
            context.fd.write(f"{name}: .space {typesize}\n")


def ipc_syscall_linux(
    context: AMD64CodegenContext,
    *,
    arguments_count: int,
    store_retval_onto_stack: bool,
    injected_args: list[int | None] | None,
) -> None:
    """Call system (syscall) and apply IPC ABI convention to arguments."""
    assert not injected_args or len(injected_args) == arguments_count + 1
    registers_to_load = (
        AMD64_LINUX_SYSCALL_NUMBER_REGISTER,
        *AMD64_LINUX_SYSCALL_ARGUMENTS_REGISTERS[:arguments_count][::-1],
    )

    if not injected_args:
        injected_args = [None for _ in range(arguments_count + 1)]

    for injected_argument, register in zip(
        injected_args,
        registers_to_load,
        strict=False,
    ):
        if injected_argument is not None:
            # Register injected and infered from stack
            store_integer_into_register(
                context,
                register=register,
                value=injected_argument,
            )
            continue
        pop_cells_from_stack_into_registers(context, register)

    context.write("syscall")

    if store_retval_onto_stack:
        # Mostly related to optimizations above if we dont want to store result
        push_register_onto_stack(context, AMD64_LINUX_ABI_RETVAL_REGISTER)


def function_end_with_epilogue(
    context: AMD64CodegenContext,
    *,
    has_return_value: bool,
) -> None:
    """Functions epilogue at the end. Restores required fields (like stack-pointer)."""
    if has_return_value:
        pop_cells_from_stack_into_registers(context, AMD64_LINUX_ABI_RETVAL_REGISTER)

    context.write("retq")


def function_begin_with_prologue(
    context: AMD64CodegenContext,
    *,
    function_name: str,
    as_global_linker_symbol: bool,
    arguments_count: int,
) -> None:
    """Begin an function symbol with prologue with preparing required (like stack-pointer).

    TODO(@kirillzhosul, @stepanzubkov): Review alignment for executable sections.
    """
    if as_global_linker_symbol:
        context.fd.write(f".global {function_name}\n")
    context.fd.write(f"{function_name}:\n")
    if arguments_count:
        registers = AMD64_LINUX_ABI_ARGUMENTS_REGISTERS[:arguments_count]
        for register in registers:
            push_register_onto_stack(context, register)


def function_call(
    context: AMD64CodegenContext,
    *,
    name: str,
    type_contract_in: Sequence[Type],
    type_contract_out: Type,
) -> None:
    """Call an function using C ABI (Gofra native and C-FFI both functions).

    As Gofra under the hood uses C call convention for functions, this simplifies differences between C and Gofra calls.
    """
    i64_arguments_count = len(type_contract_in)
    store_return_value = not isinstance(type_contract_out, VoidType)

    argument_registers = AMD64_LINUX_ABI_ARGUMENTS_REGISTERS[:i64_arguments_count][::-1]
    if i64_arguments_count > len(argument_registers):
        msg = (
            f"C-FFI function call with {i64_arguments_count} arguments not supported. "
            f"Maximum {len(argument_registers)} register arguments supported. "
            "Stack argument passing not implemented."
        )
        raise NotImplementedError(msg)

    if i64_arguments_count < 0:
        msg = f"Tried to call function `{name}` with negative arguments count"
        raise ValueError(msg)

    if i64_arguments_count:
        pop_cells_from_stack_into_registers(context, *argument_registers)

    context.write(f"callq {name}")

    if store_return_value:
        push_register_onto_stack(context, AMD64_LINUX_ABI_RETVAL_REGISTER)


def store_into_memory_from_stack_arguments(context: AMD64CodegenContext) -> None:
    """Store value from into memory pointer, pointer and value acquired from stack."""
    pop_cells_from_stack_into_registers(context, "rax", "rbx")
    context.write("movq rax, (rbx)")


def load_memory_from_stack_arguments(context: AMD64CodegenContext) -> None:
    """Load memory as value using arguments from stack."""
    pop_cells_from_stack_into_registers(context, "rax")
    context.write("movq (rax), rax")
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
            context.write("addq rbx, rax")
        case "-":
            context.write("subq rax, rbx")
        case "*":
            context.write("mulq rbx, rax")
        case "//":
            raise NotImplementedError
        case "%":
            raise NotImplementedError
        case "&&" | "||" | "|" | "&" | ">>" | "<<":
            raise NotImplementedError
        case "++":
            context.write("incq rax")
        case "--":
            context.write("decq rax")
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
                "cmpq rbx, rax",
                "xorq rax, rax",
                f"set{logic_op[operation]}b al",
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
        "cmpq $0, rax",
        f"je {jump_over_label}",
    )
