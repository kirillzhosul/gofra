"""Assembly abstraction layer that hides declarative assembly OPs into functions that generates that for you."""

from __future__ import annotations

from typing import TYPE_CHECKING

from gofra.cli.output import cli_message
from gofra.codegen.backends.aarch64_macos.frame import (
    build_local_variables_frame_offsets,
    preserve_calee_frame,
    restore_calee_frame,
)
from gofra.hir.operator import OperatorType
from gofra.hir.variable import VariableIntArrayInitializerValue
from gofra.types._base import PrimitiveType
from gofra.types.composite.array import ArrayType
from gofra.types.primitive.character import CharType
from gofra.types.primitive.integers import I64Type
from gofra.types.primitive.void import VoidType

from .registers import (
    AARCH64_DOUBLE_WORD_BITS,
    AARCH64_GP_REGISTERS,
    AARCH64_HALF_WORD_BITS,
    AARCH64_STACK_ALIGNMENT,
    AARCH64_STACK_ALIGNMENT_BIN,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from gofra.codegen.abi import AARCH64ABI
    from gofra.codegen.backends.aarch64_macos._context import AARCH64CodegenContext
    from gofra.hir.variable import Variable
    from gofra.types._base import Type

# Static symbol (data) sections
SYM_SECTION_BSS = "__DATA,__bss"
SYM_SECTION_DATA = "__DATA,__data"
SYM_SECTION_CSTR = "__TEXT,__cstring,cstring_literals"


def drop_stack_slots(
    context: AARCH64CodegenContext,
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
    context.write(f"add SP, SP, #{shift_in_bits}")


def pop_cells_from_stack_into_registers(
    context: AARCH64CodegenContext,
    *registers: AARCH64_GP_REGISTERS,
) -> None:
    """Pop cells from stack and store into given registers.

    Each cell is 8 bytes, but stack pointer is always adjusted by `AARCH64_STACK_ALIGNMENT` bytes
    to preserve stack alignment.
    """
    assert registers, "Expected registers to store popped result into!"

    for register in registers:
        context.write(
            f"ldr {register}, [SP]",
            f"add SP, SP, #{AARCH64_STACK_ALIGNMENT}",
        )


def push_register_onto_stack(
    context: AARCH64CodegenContext,
    register: AARCH64_GP_REGISTERS,
) -> None:
    """Store given register onto stack under current stack pointer."""
    context.write(f"str {register}, [SP, -{AARCH64_STACK_ALIGNMENT}]!")


def store_integer_into_register(
    context: AARCH64CodegenContext,
    register: AARCH64_GP_REGISTERS,
    value: int,
) -> None:
    """Store given value into given register."""
    context.write(f"mov {register}, #{value}")


def push_float_onto_stack(context: AARCH64CodegenContext, value: float) -> None:
    assert value > 0
    context.float_constants[value] = f"__gofra_float{len(context.float_constants)}"
    f_const = context.float_constants[value]
    context.write(f"adrp X0, {f_const}@PAGE")
    context.write(f"ldr D0, [X0, {f_const}@PAGEOFF]")
    push_register_onto_stack(context, register="D0")


def push_integer_onto_stack(
    context: AARCH64CodegenContext,
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

    context.write("// push integer")
    if value <= AARCH64_HALF_WORD_BITS:
        # We have small immediate value which we may just store without shifts
        context.write(f"mov X0, #{value}")
        if is_negative:
            context.write("sub X0, XZR, X0")
        push_register_onto_stack(context, register="X0")
        return

    preserve_bits = False
    for shift in range(0, 64, 16):
        chunk = hex((value >> shift) & AARCH64_HALF_WORD_BITS)
        if chunk == "0x0":
            # Zeroed chunk so we dont push it as register is zeroed
            continue

        if not preserve_bits:
            # Store upper bits
            context.write(f"movz X0, #{chunk}, lsl #{shift}")
            preserve_bits = True
            continue

        # Store lower bits
        context.write(f"movk X0, #{chunk}, lsl #{shift}")

    if is_negative:
        context.write("sub X0, XZR, X0")

    push_register_onto_stack(context, register="X0")


def push_static_address_onto_stack(
    context: AARCH64CodegenContext,
    segment: str,
) -> None:
    """Push executable static memory address onto stack with page dereference."""
    context.write(
        f"adrp X0, {segment}@PAGE",
        f"add X0, X0, {segment}@PAGEOFF",
    )
    push_register_onto_stack(context, register="X0")


def push_local_variable_address_from_frame_offset(
    context: AARCH64CodegenContext,
    local_variables: Mapping[str, Variable[Type]],
    local_variable: str,
) -> None:
    # Calculate negative offset from X29
    current_offset = build_local_variables_frame_offsets(local_variables).offsets[
        local_variable
    ]

    context.write(
        "mov X0, X29",
        f"sub X0, X0, #{current_offset}",
    )
    push_register_onto_stack(context, register="X0")


def evaluate_conditional_block_on_stack_with_jump(
    context: AARCH64CodegenContext,
    jump_over_label: str,
) -> None:
    """Evaluate conditional block by popping current value under SP against zero.

    If condition is false (value on stack) then jump out that conditional block to `jump_over_label`
    """
    pop_cells_from_stack_into_registers(context, "X0")
    context.write(
        "cmp X0, #0",
        f"beq {jump_over_label}",
    )


def initialize_static_data_section(
    context: AARCH64CodegenContext,
    static_strings: Mapping[str, str],
    static_variables: Mapping[str, Variable[Type]],
) -> None:
    """Initialize data section fields with given values.

    Section is an tuple (label, data)
    Data is an string (raw ASCII) or number (zeroed memory blob)
    """
    if static_strings:
        context.fd.write(f".section {SYM_SECTION_CSTR}\n")
        for name, data in static_strings.items():
            context.fd.write(f'{name}: .asciz "{data}"\n')

    bss_variables = {
        k: v for k, v in static_variables.items() if v.initial_value is None
    }
    data_variables = {
        k: v for k, v in static_variables.items() if v.initial_value is not None
    }

    if bss_variables:
        context.fd.write(f".section {SYM_SECTION_BSS}\n")
        for name, variable in bss_variables.items():
            type_size = variable.size_in_bytes
            if type_size == 0:
                cli_message(
                    "WARNING",
                    f"Variable {variable.name} has zero byte size (type {variable.type}) this variable will be not defined as symbol!",
                )
            else:
                # TODO(@kirillzhosul): review realignment of static variables
                if type_size >= 32:
                    context.fd.write(".p2align 4\n")
                else:
                    context.fd.write(".p2align 3\n")
                assert variable.initial_value is None
                context.fd.write(f"{name}: .space {type_size}\n")

    if data_variables or context.float_constants:
        context.fd.write(f".section {SYM_SECTION_DATA}\n")
        for float_v, float_n in context.float_constants.items():
            context.fd.write(f"{float_n}: .double {float_v}")
        for name, variable in data_variables.items():
            assert name not in context.float_constants.values()
            _write_static_segment_const_variable_initializer(
                context,
                variable,
                symbol_name=name,
            )


def _write_static_segment_const_variable_initializer(
    context: AARCH64CodegenContext,
    variable: Variable[Type],
    symbol_name: str,
) -> None:
    type_size = variable.size_in_bytes

    assert variable.initial_value is not None
    match variable.type:
        case CharType() | I64Type():
            if type_size == 0:
                cli_message(
                    "WARNING",
                    f"Variable {variable.name} has zero byte size (type {variable.type}) this variable will be not defined as symbol!",
                )
                return
            # TODO(@kirillzhosul): review realignment of static variables
            if type_size >= 32:
                context.fd.write(".p2align 4\n")
            else:
                context.fd.write(".p2align 3\n")

            ddd = _get_ddd_for_type(variable.type)
            context.fd.write(f"{symbol_name}: {ddd} {variable.initial_value}\n")
        case ArrayType(element_type=I64Type()):
            assert isinstance(variable.initial_value, VariableIntArrayInitializerValue)
            ddd = _get_ddd_for_type(I64Type())

            values = variable.initial_value.values
            f_values = ", ".join(map(str, values))

            context.fd.write(f"{symbol_name}: \n\t{ddd} {f_values}\n")
            assert variable.initial_value.default == 0, "Not implemented"
            if variable.initial_value.default == 0:
                # Zero initialized symbol
                # TODO(@kirillzhosul): Alignment
                assert variable.type.elements_count, "Got incomplete array type"
                element_size = variable.type.element_type.size_in_bytes
                bytes_total = element_size * variable.type.elements_count
                bytes_taken = len(values) * element_size
                bytes_free = bytes_total - bytes_taken
                context.fd.write(f"\t.zero {bytes_free}\n")

        case _:
            msg = f"Has no known initializer codegen logic for type {variable.type}"
            raise ValueError(msg)


def _get_ddd_for_type(t: PrimitiveType) -> str:
    """Get Data Definition Directive for type based on byte size."""
    type_size = t.size_in_bytes
    if type_size <= 1:
        return ".byte"
    if type_size <= 2:
        return ".half"
    if type_size <= 4:
        return ".word"
    if type_size <= 8:
        return ".quad"
    msg = f"Cannot get DDD for symbol of type {t}, max byte size is capped"
    raise ValueError(msg)


def ipc_syscall_macos(
    context: AARCH64CodegenContext,
    *,
    arguments_count: int,
    store_retval_onto_stack: bool,
    injected_args: Sequence[int | None] | None,
) -> None:
    """Call system (syscall) via supervisor call and apply IPC ABI convention to arguments."""
    assert not injected_args or len(injected_args) == arguments_count + 1

    if not injected_args:
        injected_args = [None for _ in range(arguments_count + 1)]

    abi = context.abi
    registers_to_load = (
        abi.syscall_number_register,
        *abi.syscall_arguments_registers[:arguments_count][::-1],
    )

    for injected_argument, register in zip(
        injected_args,
        registers_to_load,
        strict=False,
    ):
        if injected_argument is not None:
            # Register injected and inferred from stack
            store_integer_into_register(
                context,
                register=register,
                value=injected_argument,
            )
            continue
        pop_cells_from_stack_into_registers(context, register)

    # Supervisor call (syscall)
    context.write("svc #0")

    # System calls always returns `long` type (e.g integer 64 bits (default one for Gofra))
    if store_retval_onto_stack:
        push_register_onto_stack(
            context,
            abi.retval_primitive_64bit_register,
        )


def perform_operation_onto_stack(
    context: AARCH64CodegenContext,
    operation: OperatorType,
) -> None:
    """Perform *math* operation onto stack (pop arguments and push back result)."""
    registers = ("X0", "X1")
    pop_cells_from_stack_into_registers(context, *registers)

    # TODO(@kirillzhosul): Optimize inc / dec (++, --) when incrementing / decrementing by known values
    context.write(f"// OP on-stack {operation}")
    match operation:
        case OperatorType.ARITHMETIC_PLUS:
            context.write("add X0, X1, X0")
        case OperatorType.ARITHMETIC_MINUS:
            context.write("sub X0, X1, X0")
        case OperatorType.ARITHMETIC_MULTIPLY:
            context.write("mul X0, X1, X0")
        case OperatorType.ARITHMETIC_DIVIDE:
            context.write("sdiv X0, X1, X0")
        case OperatorType.ARITHMETIC_MODULUS:
            context.write(
                "udiv X2, X1, X0",
                "mul X2, X2, X0",
                "sub X0, X1, X2",
            )
        case OperatorType.LOGICAL_OR | OperatorType.BITWISE_OR:
            # Use bitwise one here even for logical one as we have typechecker which expects boolean types.
            context.write("orr X0, X0, X1")
        case OperatorType.SHIFT_RIGHT:
            context.write("lsr X0, X1, X0")
        case OperatorType.SHIFT_LEFT:
            context.write("lsl X0, X1, X0")
        case OperatorType.BITWISE_AND | OperatorType.LOGICAL_AND:
            # Use bitwise one here even for logical one as we have typechecker which expects boolean types.
            context.write("and X0, X0, X1")
        case OperatorType.BITWISE_XOR:
            context.write("eor X0, X0, X1")

        case (
            OperatorType.COMPARE_EQUALS
            | OperatorType.COMPARE_GREATER
            | OperatorType.COMPARE_GREATER_EQUALS
            | OperatorType.COMPARE_LESS
            | OperatorType.COMPARE_NOT_EQUALS
            | OperatorType.COMPARE_LESS_EQUALS
        ):
            logic_op = {
                OperatorType.COMPARE_NOT_EQUALS: "ne",
                OperatorType.COMPARE_GREATER_EQUALS: "ge",
                OperatorType.COMPARE_LESS_EQUALS: "le",
                OperatorType.COMPARE_LESS: "lt",
                OperatorType.COMPARE_GREATER: "gt",
                OperatorType.COMPARE_EQUALS: "eq",
            }
            context.write(
                "cmp X1, X0",
                f"cset X0, {logic_op[operation]}",
            )
        case _:
            msg = f"{operation} cannot be performed by codegen `{perform_operation_onto_stack.__name__}`"
            raise ValueError(msg)
    push_register_onto_stack(context, "X0")


def load_memory_from_stack_arguments(context: AARCH64CodegenContext) -> None:
    """Load memory as value using arguments from stack."""
    pop_cells_from_stack_into_registers(context, "X0")
    context.write("ldr X0, [X0]")
    push_register_onto_stack(context, "X0")


def store_into_memory_from_stack_arguments(context: AARCH64CodegenContext) -> None:
    """Store value into memory pointer, pointer and value acquired from stack."""
    pop_cells_from_stack_into_registers(context, "X0", "X1")
    context.write("str X0, [X1]")


def function_begin_with_prologue(  # noqa: PLR0913
    context: AARCH64CodegenContext,
    *,
    name: str,
    global_name: str | None = None,
    preserve_frame: bool = True,
    local_variables: Mapping[str, Variable[Type]],
    arguments_count: int,
) -> None:
    """Begin an function symbol.

    Injects prologue with preparing required state (e.g registers, frame/stack pointers)

    :is_global_symbol: Mark that function symbol as global for linker
    :preserve_frame: If true will preserve function state for proper stack management and return address
    """
    local_offsets = build_local_variables_frame_offsets(local_variables)
    if global_name:
        context.fd.write(f".global {global_name}\n")

    context.fd.write(f".align {AARCH64_STACK_ALIGNMENT_BIN}\n")
    context.fd.write(f"{name}:\n")

    if preserve_frame:
        preserve_calee_frame(context, local_space_size=local_offsets.local_space_size)

    abi = context.abi
    if arguments_count:
        registers = abi.arguments_64bit_registers[:arguments_count]
        context.write("// C-FFI arguments")
        for register in registers:
            push_register_onto_stack(context, register)

    for variable in local_variables.values():
        initial_value = variable.initial_value
        if initial_value is None:
            continue

        current_offset = local_offsets.offsets[variable.name]
        _write_initializer_for_stack_variable(
            context,
            initial_value,
            variable.type,
            current_offset,
        )


def _write_initializer_for_stack_variable(
    context: AARCH64CodegenContext,
    initial_value: int | VariableIntArrayInitializerValue,
    var_type: Type,
    offset: int,
) -> None:
    if initial_value == 0:
        # wzr for 32 bits later
        context.write(f"str XZR, [X29, -{offset}]")

    if isinstance(initial_value, VariableIntArrayInitializerValue):
        assert isinstance(var_type, ArrayType)
        for i, value in enumerate(initial_value.values):
            element_relative_offset = var_type.get_index_offset(i)
            context.write(f"mov X0, #{value}")
            context.write(f"str X0, [X29, -{offset - element_relative_offset}]")
        return

    # Default int initializer
    context.write(f"mov X0, #{initial_value}")
    context.write(f"str X0, [X29, -{offset}]")


def function_end_with_epilogue(
    context: AARCH64CodegenContext,
    *,
    has_preserved_frame: bool = True,
    execution_trap_instead_return: bool = False,
    return_type: Type,
) -> None:
    """End function with proper epilogue.

    Epilogue is required to proper restore required state (e.g registers, frame/stack pointers)
    and possibly cleanup.

    :has_preserved_frame: If true, will restore that to jump out and proper stack management
    :execution_trap_instead_return: Internal, if true, will replace simple return with execution guard trap to raise from execution
    """
    if not isinstance(return_type, VoidType):
        if return_type.size_in_bytes == 0:
            msg = "Cannot return value with size in bytes zero!"
            raise ValueError(msg)
        acquire_return_value_from_abi_call(context, context.abi, return_type)

    if has_preserved_frame:
        restore_calee_frame(context)

    if execution_trap_instead_return:
        execution_guard_trap(context)
        return

    context.write("ret")


def debugger_breakpoint_trap(context: AARCH64CodegenContext, number: int) -> None:
    """Place an debugger breakpoint (e.g trace trap).

    Will halt execution to the debugger, useful for debugging purposes.
    Also due to being an trap (e.g execution will be caught) allows to trap some execution places.
    (e.g start entry exit failure)
    """
    if not (0 <= number <= AARCH64_HALF_WORD_BITS):
        msg = "Expected 16-bit immediate for breakpoint trap number!"
        raise ValueError(msg)
    context.write(f"brk #{number & AARCH64_HALF_WORD_BITS}")


def execution_guard_trap(context: AARCH64CodegenContext) -> None:
    """Place a trap to prevent execution after function return.

    Prevents fatal errors when execution falls through exit call into
    unbound memory.
    """
    debugger_breakpoint_trap(context, number=0)


def function_call(
    context: AARCH64CodegenContext,
    *,
    name: str,
    type_contract_in: Sequence[Type],
    type_contract_out: Type,
) -> None:
    """Call an function using C ABI (Gofra native and C-FFI both functions).

    As Gofra under the hood uses C call convention for functions, this simplifies differences between C and Gofra calls.

    Uses Branch-With-Link (BL) instruction to `jump` into an function and passing Link-Register (LR, x30 on AARCH64) to callee
    Passes arguments before function call with C call convention (e.g via registers and stack depending on arguments byte size and type),
    Restores single return value if requested from retval register.

    Most of the call logic is covered into function own prologue, which unpacks arguments and stores calee stack frame
    """
    abi = context.abi

    integer_arguments_count = len(type_contract_in)
    store_return_value = not isinstance(type_contract_out, VoidType)

    if integer_arguments_count > len(abi.arguments_64bit_registers):
        msg = (
            f"C-FFI function call with {integer_arguments_count} arguments not supported. "
            f"Maximum {len(context.abi.arguments_64bit_registers)} register arguments supported. "
            "Stack argument passing not implemented."
        )
        raise NotImplementedError(msg)

    if integer_arguments_count < 0:
        msg = f"Tried to call function `{name}` with negative arguments count"
        raise ValueError(msg)

    if integer_arguments_count:
        registers = abi.arguments_64bit_registers[:integer_arguments_count][::-1]
        context.write("// C-FFI arguments")
        pop_cells_from_stack_into_registers(context, *registers)

    context.write(f"bl {name}")

    if store_return_value:
        retval_t = type_contract_out
        if retval_t.size_in_bytes <= 4:
            # Primitive return value as 32 bit
            # directly store into return register (lower 32 bits)
            push_register_onto_stack(context, abi.retval_primitive_32bit_register)
        elif retval_t.size_in_bytes <= 8:
            # Primitive return value as 64 bit
            # directly store into return register (full 64 bits)
            push_register_onto_stack(context, abi.retval_primitive_64bit_register)
        elif retval_t.size_in_bytes <= 16:
            # Composite return value up to 128 bits
            # store two segments as registers where lower bytes are in first register (always 64 bit)
            # and remaining bytes in second register
            push_register_onto_stack(context, abi.retval_primitive_64bit_register)
            remaining_bytes = retval_t.size_in_bytes - 8
            if remaining_bytes <= 4:
                push_register_onto_stack(context, abi.retval_composite_32bit_register)
            else:
                push_register_onto_stack(context, abi.retval_composite_64bit_register)
        else:
            msg = "Indirect allocation required, not implemented!"
            raise ValueError(msg)


def acquire_return_value_from_abi_call(
    context: AARCH64CodegenContext,
    abi: AARCH64ABI,
    retval: Type,
) -> None:
    if retval.size_in_bytes <= 4:
        # Primitive return value as 32 bit
        # directly store into return register (lower 32 bits)
        pop_cells_from_stack_into_registers(
            context,
            abi.retval_primitive_32bit_register,
        )
    elif retval.size_in_bytes <= 8:
        # Primitive return value as 64 bit
        # directly store into return register (full 64 bits)
        pop_cells_from_stack_into_registers(
            context,
            abi.retval_primitive_64bit_register,
        )
    elif retval.size_in_bytes <= 16:
        # Composite return value up to 128 bits
        # store two segments as registers where lower bytes are in first register (always 64 bit)
        # and remaining bytes in second register
        pop_cells_from_stack_into_registers(
            context,
            abi.retval_primitive_64bit_register,
        )
        remaining_bytes = retval.size_in_bytes - 8
        if remaining_bytes <= 4:
            pop_cells_from_stack_into_registers(
                context,
                abi.retval_composite_32bit_register,
            )
        else:
            pop_cells_from_stack_into_registers(
                context,
                abi.retval_composite_64bit_register,
            )
    else:
        msg = "Indirect allocation required, not implemented!"
        raise ValueError(msg)
