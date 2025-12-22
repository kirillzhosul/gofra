from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

from gofra.cli.goals._optimization_pipeline import cli_process_optimization_pipeline
from gofra.cli.output import cli_fatal_abort
from libgofra.gofra import process_input_file
from libgofra.hir.operator import FunctionCallOperand, Operator, OperatorType
from libgofra.lexer.tokens import TokenLocation
from libgofra.preprocessor.macros.registry import registry_from_raw_definitions

if TYPE_CHECKING:
    from gofra.cli.parser.arguments import CLIArguments
    from libgofra.hir.function import Function
    from libgofra.hir.module import Module

FULL_DEPENDENCY_GRAPH_HIR = True
DISPLAY_FUNCTION_BODY = False


def cli_perform_hir_goal(args: CLIArguments) -> NoReturn:
    """Perform HIR display only goal that emits HIR operators into stdout."""
    assert args.hir, "Cannot perform HIR goal with no HIR flag set!"
    assert not args.lexer_debug_emit_lexemes, "Try use compile goal"

    if args.output_file_is_specified:
        return cli_fatal_abort(
            text="Output file has no effect for HIR only goal, please pipe output via posix pipe (`>`) into desired file!",
        )

    if len(args.source_filepaths) > 1:
        return cli_fatal_abort(
            text="Multiple source files has not effect for HIR only goal, as it has no linkage, please specify single file!",
        )

    macros_registry = registry_from_raw_definitions(
        location=TokenLocation.cli(),
        definitions=args.definitions,
    ).inject_propagated_defaults(target=args.target)

    module = process_input_file(
        args.source_filepaths[0],
        args.include_paths,
        macros=macros_registry,
        rt_array_oob_check=args.runtime_array_oob_checks,
    )

    cli_process_optimization_pipeline(module, args)
    if FULL_DEPENDENCY_GRAPH_HIR:
        for dep in module.visit_dependencies(include_self=True):
            _emit_hir_into_stdout(dep)
    else:
        _emit_hir_into_stdout(module)
    return sys.exit(0)


def display_relative(path: Path | str) -> str:
    """Display path relative to cwd if possible, else absolute."""
    path = Path(path).resolve()
    cwd = Path.cwd()

    try:
        return str(path.relative_to(cwd))
    except ValueError:
        return str(path)


def _emit_hir_into_stdout(module: Module) -> None:
    """Display IR via stdout."""
    print("HIR module:", display_relative(module.path))
    print(
        "Flat dependency graph:",
        ", ".join(
            str(display_relative(p))
            for p in module.flatten_dependencies_paths(include_self=False)
        )
        if module.dependencies
        else "none",
    )
    if not DISPLAY_FUNCTION_BODY:
        return
    for function in module.functions.values():
        _emit_ir_function_signature(function)
        context_block_shift = 0
        for operator in function.operators:
            if operator.type in (
                OperatorType.CONDITIONAL_DO,
                OperatorType.CONDITIONAL_END,
            ):
                context_block_shift -= 1
            _emit_ir_operator(operator, context_block_shift=context_block_shift)
            if operator.type in (
                OperatorType.CONDITIONAL_DO,
                OperatorType.CONDITIONAL_IF,
                OperatorType.CONDITIONAL_WHILE,
                OperatorType.CONDITIONAL_FOR,
            ):
                context_block_shift += 1


def _emit_ir_operator(operator: Operator, context_block_shift: int) -> None:  # noqa: PLR0911
    shift = " " * (context_block_shift + 3)
    match operator.type:
        case OperatorType.PUSH_INTEGER:
            return print(f"{shift}PUSH {operator.operand}")
        case (
            OperatorType.CONDITIONAL_WHILE
            | OperatorType.CONDITIONAL_IF
            | OperatorType.CONDITIONAL_FOR
        ):
            return print(f"{shift}{operator.type.name}" + "{")
        case OperatorType.CONDITIONAL_DO:
            return print(f"{shift}" + "}" + f"{operator.type.name}" + "{")
        case OperatorType.CONDITIONAL_END:
            return print(f"{shift}" + "}")
        case OperatorType.FUNCTION_CALL:
            if isinstance(operator.operand, FunctionCallOperand):
                mod = operator.operand.module
                func = operator.operand.func_name
                return print(f"{shift}{mod}.{func}()")
            return print(f"{shift}{operator.operand}()")
        case _:
            if operator.operand:
                return print(f"{shift}{operator.type.name}<{operator.operand}>")
            return print(f"{shift}{operator.type.name}")


def _emit_ir_function_signature(function: Function) -> None:
    if function.is_external:
        print(f"[external function symbol '{function.name}'", end=" ")
        print(f"({function.parameters} -> {function.return_type})")
        return
    print(f"[function symbol '{function.name}'", end=" ")
    print(f"({function.parameters} -> {function.return_type})", end=" ")
    print(f"(public={function.is_public})]", end=" ")
    print(f"({len(function.variables)} local variables)", end=" ")
    if function.is_leaf:
        print("[has_leaf_property]", end="")
    print()
