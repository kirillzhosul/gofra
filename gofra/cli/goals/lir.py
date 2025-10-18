from __future__ import annotations

import sys
from typing import TYPE_CHECKING, NoReturn

from gofra.cli.goals._optimization_pipeline import cli_process_optimization_pipeline
from gofra.cli.output import cli_message
from gofra.codegen.lir import LIRProgram, translate_hir_to_lir
from gofra.codegen.lir.registers import LIRVirtualRegisterAllocator
from gofra.codegen.lir.static import (
    LIRStaticSegmentCString,
    LIRStaticSegmentGlobalVariable,
)
from gofra.gofra import process_input_file
from gofra.lexer.tokens import TokenLocation
from gofra.preprocessor.macros.registry import registry_from_raw_definitions

if TYPE_CHECKING:
    from gofra.cli.parser.arguments import CLIArguments


def cli_perform_lir_goal(args: CLIArguments) -> NoReturn:
    """Perform LIR display only goal that emits LIR operators into stdout."""
    assert args.lir, "Cannot perform LIR goal with no LIR flag set!"
    assert not args.lexer_debug_emit_lexemes, "Try use compile goal"

    if args.output_file_is_specified:
        cli_message(
            "ERROR",
            "Output file has no effect for LIR only goal, please pipe output via posix pipe (`>`) into desired file!",
        )
        return sys.exit(1)

    if len(args.source_filepaths) > 1:
        cli_message(
            "ERROR",
            "Multiple source files has not effect for LIR only goal, as it has no linkage, please specify single file!",
        )
        return sys.exit(1)

    macros_registry = registry_from_raw_definitions(
        location=TokenLocation.cli(),
        definitions=args.definitions,
    ).inject_propagated_defaults(target=args.target)

    module = process_input_file(
        args.source_filepaths[0],
        args.include_paths,
        macros=macros_registry,
        _debug_emit_lexemes=args.lexer_debug_emit_lexemes,
    )

    cli_process_optimization_pipeline(module, args)

    lir = translate_hir_to_lir(
        module,
        system_entry_point_name="TARGET_SPECIFIC_ENTRY_POINT",
        virtual_register_allocator=LIRVirtualRegisterAllocator(
            list(map(str, range(100))),
        ),
    )

    _emit_lir_into_stdout(lir)
    return sys.exit(0)


def _emit_lir_into_stdout(lir: LIRProgram) -> None:
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
