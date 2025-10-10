"""Intermediate representation for CLI.

Allows to view IR from CLI.
"""

from gofra.codegen.lir import translate_hir_to_lir
from gofra.codegen.lir.registers import LIRVirtualRegisterAllocator
from gofra.codegen.lir.static import (
    LIRStaticSegmentCString,
    LIRStaticSegmentGlobalVariable,
)
from gofra.consts import GOFRA_ENTRY_POINT
from gofra.context import ProgramContext
from gofra.hir.function import Function
from gofra.hir.operator import Operator, OperatorType


def emit_hir_into_stdout(context: ProgramContext) -> None:
    """Display IR via stdout."""
    functions = {**context.functions, GOFRA_ENTRY_POINT: context.entry_point}
    for function in functions.values():
        emit_ir_function_signature(function, context.entry_point)
        context_block_shift = 0
        for operator in function.operators:
            if operator.type in (
                OperatorType.CONDITIONAL_DO,
                OperatorType.CONDITIONAL_END,
            ):
                context_block_shift -= 1
            emit_ir_operator(operator, context_block_shift=context_block_shift)
            if operator.type in (
                OperatorType.CONDITIONAL_DO,
                OperatorType.CONDITIONAL_IF,
                OperatorType.CONDITIONAL_WHILE,
            ):
                context_block_shift += 1


def emit_lir_into_stdout(context: ProgramContext) -> None:
    lir = translate_hir_to_lir(
        context,
        system_entry_point_name="TARGET_SPECIFIC_ENTRY_POINT",
        virtual_register_allocator=LIRVirtualRegisterAllocator(
            list(map(str, range(100))),
        ),
    )

    print("--- LIR static segment start --- ")
    sizeof_static = 0
    for seg in lir.static_segment.values():
        if isinstance(seg, LIRStaticSegmentCString):
            print("\t Static C-String", f"'{seg.name}'")
            sizeof_static += len(seg.text)
    for seg in lir.static_segment.values():
        if isinstance(seg, LIRStaticSegmentGlobalVariable):
            print(
                f"\t Global Var '{seg.type}'",
                f"'{seg.name}'",
                f"{seg.type.size_in_bytes} bytes",
            )
            sizeof_static += seg.type.size_in_bytes

    print(f"--- LIR static segment end {sizeof_static} bytes total --- ")
    print("--- LIR externs declaration start --- ")
    for e in lir.externs.values():
        print(
            "\t",
            f"'{e.return_type} {e.name}({', '.join(repr(p.type) for p in e.parameters)})'",
            f"real_name='{e.real_name}'" if e.real_name != e.name else "",
        )
    print("--- LIR externs declaration end --- ")
    print("--- LIR internal functions declaration start --- ")
    instr_counter = 0
    for f in lir.functions.values():
        print(
            "\t",
            f"'{f.return_type} {f.name}({', '.join(repr(p.type) for p in f.parameters)})'",
            f"{len(f.locals)} locals",
        )
        for op in f.operations:
            print("\t\t", repr(op))
            instr_counter += 1
    print("--- LIR internal functions declaration end --- ")
    print(f"[Total LIR instructions: {instr_counter}]")


def emit_ir_operator(operator: Operator, context_block_shift: int) -> None:
    shift = " " * (context_block_shift + 3)
    match operator.type:
        case OperatorType.PUSH_INTEGER:
            return print(f"{shift}PUSH {operator.operand}")
        case OperatorType.CONDITIONAL_WHILE | OperatorType.CONDITIONAL_IF:
            return print(f"{shift}{operator.type.name}" + "{")
        case OperatorType.CONDITIONAL_DO:
            return print(f"{shift}" + "}" + f"{operator.type.name}" + "{")
        case OperatorType.CONDITIONAL_END:
            return print(f"{shift}" + "}")
        case OperatorType.FUNCTION_CALL:
            return print(f"{shift}{operator.operand}()")
        case _:
            return print(f"{shift}{operator.type.name}<{operator.operand}>")


def emit_ir_function_signature(function: Function, entry_point: Function) -> None:
    if function.is_external:
        print(f"[external function symbol '{function.name}'", end=" ")
        print(f"({function.parameters} -> {function.return_type})")
        return
    if function == entry_point:
        print(f"[entry point symbol '{function.name}']")
        return
    print(f"[function symbol '{function.name}'", end=" ")
    print(f"({function.parameters} -> {function.return_type})", end=" ")
    print(f"(global={function.is_global})]", end=" ")
    print(f"({len(function.variables)} local variables)", end=" ")
    if function.is_leaf:
        print("[has_leaf_property]", end="")
    print()
