from __future__ import annotations

import sys
from typing import TYPE_CHECKING, NoReturn

from gofra.cli.goals._optimization_pipeline import cli_process_optimization_pipeline
from gofra.cli.output import cli_message
from libgofra.gofra import process_input_file
from libgofra.hir.operator import Operator, OperatorType
from libgofra.lexer.tokens import TokenLocation
from libgofra.preprocessor.macros.registry import registry_from_raw_definitions

if TYPE_CHECKING:
    from gofra.cli.parser.arguments import CLIArguments
    from libgofra.hir.function import Function
    from libgofra.hir.module import Module


def cli_perform_hir_goal(args: CLIArguments) -> NoReturn:
    """Perform HIR display only goal that emits HIR operators into stdout."""
    assert args.hir, "Cannot perform HIR goal with no HIR flag set!"
    assert not args.lexer_debug_emit_lexemes, "Try use compile goal"

    if args.output_file_is_specified:
        cli_message(
            "ERROR",
            "Output file has no effect for HIR only goal, please pipe output via posix pipe (`>`) into desired file!",
        )
        return sys.exit(1)

    if len(args.source_filepaths) > 1:
        cli_message(
            "ERROR",
            "Multiple source files has not effect for HIR only goal, as it has no linkage, please specify single file!",
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
    )

    cli_process_optimization_pipeline(module, args)
    _emit_hir_into_stdout(module)
    return sys.exit(0)


def _emit_hir_into_stdout(module: Module) -> None:
    """Display IR via stdout."""
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
    print(f"(global={function.is_global})]", end=" ")
    print(f"({len(function.variables)} local variables)", end=" ")
    if function.is_leaf:
        print("[has_leaf_property]", end="")
    print()
