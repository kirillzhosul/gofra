"""Assembly abstraction layer that hides declarative assembly OPs into functions that generates that for you."""

from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from gofra.cli.output import cli_message
from gofra.codegen.backends.aarch64.primitive_instructions import (
    pop_cells_from_stack_into_registers,
    push_register_onto_stack,
    store_integer_into_register,
)
from gofra.codegen.backends.aarch64.registers import (
    AARCH64_HALF_WORD_BITS,
    AARCH64_STACK_ALIGNMENT_BIN,
)
from gofra.codegen.backends.aarch64_macos.abi_call_convention import (
    load_return_value_from_stack_into_abi_registers,
)
from gofra.codegen.backends.aarch64_macos.frame import (
    preserve_calee_frame,
    restore_calee_frame,
)
from gofra.codegen.frame import build_local_variables_frame_offsets
from gofra.hir.initializer import (
    T_AnyVariableInitializer,
    VariableIntArrayInitializerValue,
    VariableIntFieldedStructureInitializerValue,
    VariableStringPtrArrayInitializerValue,
    VariableStringPtrInitializerValue,
)
from gofra.hir.operator import OperatorType
from gofra.types._base import PrimitiveType
from gofra.types.composite.array import ArrayType
from gofra.types.composite.pointer import PointerType
from gofra.types.composite.string import StringType
from gofra.types.composite.structure import StructureType
from gofra.types.primitive.character import CharType
from gofra.types.primitive.integers import I64Type

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from gofra.codegen.backends.aarch64._context import AARCH64CodegenContext
    from gofra.hir.variable import Variable
    from gofra.types._base import Type

# Static symbol (data) sections
SYM_SECTION_BSS = "__DATA,__bss"
SYM_SECTION_DATA = "__DATA,__data"
SYM_SECTION_CSTR = "__TEXT,__cstring,cstring_literals"


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
    context.write(f"cbz X0, {jump_over_label}")


def initialize_static_data_section(
    context: AARCH64CodegenContext,
    static_strings: Mapping[str, str],
    static_variables: Mapping[str, Variable[Type]],
) -> None:
    """Initialize data section fields with given values.

    Section is an tuple (label, data)
    Data is an string (raw ASCII) or number (zeroed memory blob)
    """
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

    if data_variables or context.float_constants or static_strings:
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

        for name, data in static_strings.items():
            context.fd.write(".p2align 3\n")
            decoded_string = data.encode().decode("unicode_escape")
            length = len(decoded_string)
            context.fd.write(f"{name}: \n\t.quad {name}d\n\t.quad {length}\n")

    # Must defined after others - string initializer may forward reference them
    # but we define them by single-pass within writing initializer
    if static_strings:
        context.fd.write(f".section {SYM_SECTION_CSTR}\n")
        for name, data in static_strings.items():
            context.fd.write(f'{name}d: .asciz "{data}"\n')


def _write_static_segment_const_variable_initializer(
    context: AARCH64CodegenContext,
    variable: Variable[Type],
    symbol_name: str,
) -> None:
    type_size = variable.size_in_bytes

    assert variable.initial_value is not None
    match variable.type:
        case CharType() | I64Type():
            assert isinstance(variable.initial_value, int)
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
                bytes_total = variable.type.size_in_bytes
                bytes_taken = len(values) * element_size
                bytes_free = bytes_total - bytes_taken
                context.fd.write(f"\t.zero {bytes_free}\n")
        case ArrayType(element_type=PointerType(points_to=StringType())):
            assert isinstance(
                variable.initial_value,
                VariableStringPtrArrayInitializerValue,
            )

            values = variable.initial_value.values
            f_values = ", ".join(map(context.load_string, values))

            context.fd.write(f"{symbol_name}: \n\t.quad {f_values}\n")

        case PointerType(points_to=StringType()):
            assert isinstance(variable.initial_value, VariableStringPtrInitializerValue)
            string_raw = variable.initial_value.string
            context.fd.write(
                f"{symbol_name}: \n\t.quad {context.load_string(string_raw)}\n",
            )
        case StructureType():
            assert isinstance(
                variable.initial_value,
                VariableIntFieldedStructureInitializerValue,
            )
            # TODO(@kirillzhosul): Validate fields types before plain initialization
            context.fd.write(f"{symbol_name}: \n")
            for t_field_name, (init_field_name, init_field_value) in zip(
                variable.type.fields_ordering,
                variable.initial_value.values.items(),
                strict=True,
            ):
                # Must initialize in same order!
                assert t_field_name == init_field_name
                field_t = variable.type.fields[t_field_name]
                assert isinstance(field_t, PrimitiveType)
                ddd = _get_ddd_for_type(field_t)
                context.fd.write(
                    f"\t{ddd} {init_field_value}\n",
                )
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
    # assume 0 - 65335 (16 bit)
    context.write("svc #0")

    # System calls always returns `long` type (e.g integer 64 bits (default one for Gofra))
    if store_retval_onto_stack:
        # TODO(@kirillzhosul): Research refactoring with using calling-convention system (e.g for system calls (syscall/cffi/fast-call convention))
        # TODO(@kirillzhosul): Research weirdness of kernel `errno`, not setting carry flag
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
    parameters: Sequence[Type],
) -> None:
    """Begin an function symbol.

    Injects prologue with preparing required state (e.g registers, frame/stack pointers)

    :is_global_symbol: Mark that function symbol as global for linker
    :preserve_frame: If true will preserve function state for proper stack management and return address
    """
    if global_name:
        context.fd.write(f".globl {global_name}\n")

    context.fd.write(f".p2align {AARCH64_STACK_ALIGNMENT_BIN // 2}\n")
    context.fd.write(f"{name}:\n")
    context.fd.write(".cfi_startproc\n")

    if preserve_frame:
        local_offsets = build_local_variables_frame_offsets(local_variables)
        preserve_calee_frame(context, local_space_size=local_offsets.local_space_size)

    abi = context.abi
    if parameters:
        registers = abi.arguments_64bit_registers[: len(parameters)]
        for register in registers:
            push_register_onto_stack(context, register)

    _write_function_local_stack_variables_initializer(
        context,
        local_variables=local_variables,
    )


def _write_function_local_stack_variables_initializer(
    context: AARCH64CodegenContext,
    *,
    local_variables: Mapping[str, Variable[Type]],
) -> None:
    local_offsets = build_local_variables_frame_offsets(local_variables)
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
    initial_value: T_AnyVariableInitializer,
    var_type: Type,
    offset: int,
) -> None:
    assert offset > 0

    if isinstance(initial_value, int):
        return _set_local_numeric_var_immediate(
            context,
            initial_value,
            var_type,
            offset,
        )

    if isinstance(initial_value, VariableIntArrayInitializerValue):
        assert isinstance(var_type, ArrayType)
        values = initial_value.values
        setters = ((var_type.get_index_offset(i), v) for i, v in enumerate(values))
        for relative_offset, value in setters:
            _set_local_numeric_var_immediate(
                context,
                value,
                var_type.element_type,
                offset=offset + relative_offset,
            )
        return None

    if isinstance(initial_value, VariableStringPtrInitializerValue):
        # Load string as static string and dispatch pointer on entry
        static_blob_sym = context.load_string(initial_value.string)
        assert isinstance(var_type, PointerType)
        context.write(
            f"adrp X0, {static_blob_sym}@PAGE",
            f"add X0, X0, {static_blob_sym}@PAGEOFF",
        )
        context.write(f"str X0, [X29, -{offset}]")
        return None

    if isinstance(
        initial_value,
        VariableIntFieldedStructureInitializerValue
        | VariableStringPtrArrayInitializerValue,
    ):  # pyright: ignore[reportUnnecessaryIsInstance]
        msg = f"{initial_value} is not implemented on-stack within codegen"
        raise NotImplementedError(msg)

    assert_never(initial_value)


def _set_local_numeric_var_immediate(
    context: AARCH64CodegenContext,
    value: int,
    t: Type,
    offset: int,
) -> None:
    """Set immediate numeric value for local variable at given offset. Respects memory store instructions."""
    assert 0 < t.size_in_bytes <= 8, "Too big type to store into"

    # Use half-word instruction set (W register, half store)
    is_hword = t.size_in_bytes <= 4
    bit_count = 8 * t.size_in_bytes
    sr = ("XZR", "WZR")[is_hword] if value == 0 else ("X0", "W0")[is_hword]

    if sr in ("X0", "W0"):
        assert value.bit_count() <= bit_count
        context.write(f"mov {sr}, #{value}")

    instr = "strb" if t.size_in_bytes == 1 else ("strh" if is_hword else "str")
    context.write(f"{instr} {sr}, [X29, -{offset}]")


def function_return(
    context: AARCH64CodegenContext,
    *,
    has_preserved_frame: bool = True,
    return_type: Type,
) -> None:
    """Return from an function.

    Emits proper epilogue to restore required state

    :has_preserved_frame: If true, will restore that to jump out and proper stack management
    """
    load_return_value_from_stack_into_abi_registers(context, t=return_type)

    if has_preserved_frame:
        restore_calee_frame(context)

    context.write("ret")


def function_end_with_epilogue(
    context: AARCH64CodegenContext,
    *,
    has_preserved_frame: bool,
    return_type: Type,
    is_early_return: bool,
) -> None:
    """End function with proper epilogue.

    Epilogue is required to proper restore required state (e.g registers, frame/stack pointers)
    and possibly cleanup.

    :has_preserved_frame: If true, will restore that to jump out and proper stack management
    :is_early_return: If true, will not emit end end of procedure symbol (e.g directly early return, not finish)
    """
    function_return(
        context,
        has_preserved_frame=has_preserved_frame,
        return_type=return_type,
    )
    if not is_early_return:
        context.fd.write(".cfi_endproc\n")


def debugger_breakpoint_trap(context: AARCH64CodegenContext, number: int) -> None:
    """Place an debugger breakpoint (e.g trace trap).

    Will halt execution to the debugger, useful for debugging purposes.
    Also due to being an trap (e.g execution will be caught) allows to trap some execution places.
    (e.g start entry exit failure)
    """
    assert 0 < number < AARCH64_HALF_WORD_BITS
    context.write(f"brk #{number}")
