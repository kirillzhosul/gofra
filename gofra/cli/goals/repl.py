"""REPL goal - Read Eval Print Loop.

Interactive usage of compiler.
"""

import contextlib
import sys
from collections.abc import MutableSequence, Sequence
from pathlib import Path
from typing import NoReturn

from gofra.cache.directory import prepare_build_cache_directory
from gofra.cli.parser.arguments import CLIArguments
from gofra.cli.readline import (
    finalize_readline,
    read_multiline_input,
    try_setup_readline,
)
from gofra.execution.execution import execute_binary_executable
from gofra.execution.permissions import apply_file_executable_permissions
from libgofra.assembler.assembler import assemble_object_from_codegen_assembly
from libgofra.codegen.generator import generate_code_for_assembler
from libgofra.consts import GOFRA_ENTRY_POINT
from libgofra.exceptions import GofraError
from libgofra.gofra import process_input_file
from libgofra.lexer.tokens import TokenLocation
from libgofra.linker.linker import link_object_files
from libgofra.linker.output_format import LinkerOutputFormat
from libgofra.linker.profile import LinkerProfile
from libgofra.preprocessor.macros.registry import (
    MacrosRegistry,
    registry_from_raw_definitions,
)
from libgofra.targets.infer_host import infer_host_target
from libgofra.typecheck.typechecker import (
    emulate_type_stack_for_operators,
    on_lint_warning_suppressed,
    validate_type_safety,
)
from libgofra.types._base import Type
from libgofra.types.composite.pointer import PointerType
from libgofra.types.composite.string import StringType
from libgofra.types.primitive.integers import I64Type

HIST_FILE = Path("~").expanduser() / ".gofra_repl_history"

# Source that is compiled separately and contains any global variables / functions that is defined within REPL session
session_loader_source: list[str] = ['#include "std"']

CACHE_SUBDIR = Path(".__repl__")
SRT_FILEPATH = CACHE_SUBDIR / "session_runtime_loader.gof"
FTE_FILEPATH = CACHE_SUBDIR / "file_to_execute.gof"

# TODO(@kirillzhosul): Clean error source if errors occurred


def cli_perform_repl_goal(args: CLIArguments) -> NoReturn:
    assert args.target == infer_host_target(), "Target must be same as host target"
    assert args.output_format == "executable"

    _print_repl_welcome_message()
    _prepare_repl(args)

    # Acquire initial copy of registry to not build every expr, just copy
    ref_macros_registry = registry_from_raw_definitions(
        location=TokenLocation.cli(),
        definitions=args.definitions,
    ).inject_propagated_defaults(target=args.target)

    while True:
        lines = _read_repl_prompt()
        _perform_input(args, lines, ref_macros_registry)


def _prepare_repl(args: CLIArguments) -> None:
    try_setup_readline(HIST_FILE)
    prepare_build_cache_directory(args.build_cache_dir)
    CACHE_SUBDIR.mkdir(parents=False, exist_ok=True)

    _assemble_loader_file(args, session_loader_source)  # Reset SRT before REPL


def _read_repl_prompt() -> list[str]:
    def _stop_and_preserve_on(line: str, line_no: int) -> bool:
        always_preserve = line.startswith("#include") or (
            line_no == 0 and line.startswith("var")
        )
        if line.strip().startswith(("func", "struct")):
            msg = "functions and structs are not implemented in REPL, they behave wrong for now!"
            raise ValueError(msg)
        return always_preserve or (
            not line.strip().endswith(("if", "do", ";"))
            and line_no == 0
            and not line.startswith(("struct", "func"))
        )

    try:
        lines = read_multiline_input(
            prompt_initial=">>> ",
            prompt_multiline="... ",
            raise_eof_on=lambda line, _: line.lower() in ("q", "quit"),
            stop_and_preserve_on=_stop_and_preserve_on,
        )
    except EOFError:
        finalize_readline(HIST_FILE)
        sys.exit(0)  # User requested exit

    return lines


def _print_repl_welcome_message() -> None:
    print("Gofra REPL")
    print("Unstable version, no warranties given, use at your own risk!")


def _assemble_loader_file(args: CLIArguments, source: list[str]) -> None:
    srt_loader = args.build_cache_dir / SRT_FILEPATH
    srt_loader.parent.mkdir(parents=True, exist_ok=True)

    srt_loader.unlink(missing_ok=True)
    with srt_loader.open("w", buffering=-1) as f:
        f.writelines(source)
        f.flush()


def _tuck_definition_stmts_for_loader(
    from_: Sequence[str],
    to: MutableSequence[str],
) -> MutableSequence[str]:
    leftover: list[str] = []
    for line in from_:
        if line.startswith(("var", "func", "type", "const", "#include")):
            to.append(line)
            continue
        leftover.append(line)
    return leftover


def _perform_input(
    args: CLIArguments,
    source: list[str],
    ref_macros_registry: MacrosRegistry,
) -> None:
    # We `tuck` something like `func` to loader and preassemble it
    source_to_execute = _tuck_definition_stmts_for_loader(source, session_loader_source)
    _assemble_loader_file(args, session_loader_source)

    if not source_to_execute:
        # Only if have immediate, otherwise just loader update
        return

    executable = _compile_file_to_execute(args, source_to_execute, ref_macros_registry)
    if executable:
        _perform_compiled_binary(executable)


def _perform_compiled_binary(executable: Path) -> None:
    """After we got any REPL binary - we just execute it as already have preview code injected into it."""
    apply_file_executable_permissions(executable)
    with contextlib.suppress(KeyboardInterrupt):
        execute_binary_executable(executable, args=[])
    print()  # It already may have newline but it always adds it


def _assemble_execute_source(source: Sequence[str], preview_expr: Sequence[str]) -> str:
    return f"""#include "session_runtime_loader.gof"
func void {GOFRA_ENTRY_POINT}[]
{"\n".join([f"\t{line}" for line in source])}
{"\n".join([f"\t{line}" for line in preview_expr])}
    return
end
"""


def _compile_file_to_execute(
    args: CLIArguments,
    source: Sequence[str],
    ref_macros_registry: MacrosRegistry,
    immediate_type_stack: MutableSequence[Type] | None = None,
) -> Path | None:
    assert not args.lexer_debug_emit_lexemes

    repl_preview_expr = _assemble_preview_expr_from_types(immediate_type_stack)
    execute_source = _assemble_execute_source(source, repl_preview_expr)
    file_to_execute = args.build_cache_dir / FTE_FILEPATH
    with file_to_execute.open("w") as f:
        f.write(execute_source)

    try:
        module = process_input_file(
            file_to_execute,
            args.include_paths,
            macros=ref_macros_registry.copy(),
        )
        assert not module.dependencies, "not implemented"
    except (
        ValueError,
        AssertionError,
        GofraError,
    ) as e:  # TODO(@kirillzhosul): Finish errors
        print(f"!!! REPL Error: {e!r}")
        return None

    if immediate_type_stack is None:
        # TODO(@kirillzhosul): This may be more performant if we inject HIR loader
        # If do not have type stack, calculate first
        entry_point = module.functions[GOFRA_ENTRY_POINT]
        new_immediate_type_stack = emulate_type_stack_for_operators(
            entry_point.operators[:-1],  # Remove last return - no meaning here
            module=module,
            initial_type_stack=[],
            on_lint_warning=on_lint_warning_suppressed,
            current_function=entry_point,
        ).types

        return _compile_file_to_execute(
            args,
            source,
            ref_macros_registry=ref_macros_registry,
            immediate_type_stack=list(new_immediate_type_stack),
        )

    if not args.skip_typecheck:
        try:
            validate_type_safety(module, on_lint_warning=on_lint_warning_suppressed)
        except (ValueError, AssertionError, GofraError) as e:
            print(f"!!! REPL Error: {e!r}")
            return None

    cache_dir = args.build_cache_dir / CACHE_SUBDIR
    assembly_filepath = (cache_dir / file_to_execute.name).with_suffix(
        args.target.file_assembly_suffix,
    )

    generate_code_for_assembler(
        assembly_filepath,
        module,
        args.target,
        on_warning=on_lint_warning_suppressed,
    )

    object_filepath = (cache_dir / file_to_execute.name).with_suffix(
        args.target.file_object_suffix,
    )

    assemble_object_from_codegen_assembly(
        assembly=assembly_filepath,
        output=object_filepath,
        target=args.target,
        additional_assembler_flags=[],
        debug_information=False,
    )

    repl_executable = (cache_dir / file_to_execute.name).with_suffix(
        args.target.file_executable_suffix,
    )
    link_object_files(
        objects=[object_filepath],
        target=args.target,
        output=repl_executable,
        output_format=LinkerOutputFormat.EXECUTABLE,
        libraries=[],
        additional_flags=[],
        libraries_search_paths=[],
        profile=LinkerProfile.DEBUG,
        cache_directory=cache_dir,
    ).check_returncode()

    return repl_executable


def _assemble_preview_expr_from_types(
    types: MutableSequence[Type] | None,
) -> list[str]:
    """Get expression(s) to display resulting value from immediate expression from user.

    REPL executes native source code, and its return type is known at compile time with help of typechecker
    This function looks at it and solves how to display that value, or drop completely

    Expr is returned as raw strings as must complete full toolchain process later
    """
    if not types:
        return []
    expr: list[str] = []

    # We must look at last element, and possible review other if required
    head_t = types.pop()

    if isinstance(head_t, PointerType):
        # Display pointer as hex-address

        ptr_format_str = f'"Addr-of `{head_t}`: "'
        if isinstance(head_t.points_to, StringType):
            str_format_str = '"String-view: `"'
            print("...str...")
            expr.extend(
                [
                    "copy",
                    f"{ptr_format_str} call print",
                    "typecast int; call print_int64_hex",  # Addr-of
                    '"\\n" print',
                    f"{str_format_str} print",
                    "print",  # Actual string view
                    '"`" print',
                ],
            )
        else:
            expr.append(f"{ptr_format_str} print")
            expr.append("typecast int; print_int64_hex")

    elif isinstance(head_t, I64Type):
        # Integer
        expr.append("print_int")

    while types:
        types.pop()
        expr.append("drop")

    return expr
