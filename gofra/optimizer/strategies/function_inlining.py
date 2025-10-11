from __future__ import annotations

from typing import TYPE_CHECKING

from gofra.parser.operators import OperatorType

if TYPE_CHECKING:
    from gofra.hir.module import Module


def optimize_function_inlining(
    program: Module,
    max_operators: int,
    max_iterations: int,
) -> None:
    """Optimize function inlining (mark small functions less than 'max_operators' as inline and resolve old reference as code block'."""
    _mark_inlineable_functions_as_inline(program, max_operators=max_operators)

    for function in program.functions.values():
        for _ in range(max_iterations):
            iteration_has_fold = False
            for idx, operator in enumerate(function.operators):
                # Iterate each function source 'max_iterations' times until all new inlined function calls is not folded.
                if operator.type != OperatorType.FUNCTION_CALL:
                    continue
                assert isinstance(operator.operand, str)
                called_function = program.functions[operator.operand]
                if not called_function.is_inline:
                    continue

                iteration_has_fold = True
                function.operators = [
                    *function.operators[:idx],
                    *called_function.operators,
                    *function.operators[idx + 1 :],
                ]

            if not iteration_has_fold:
                break


def _mark_inlineable_functions_as_inline(
    program: Module,
    max_operators: int,
) -> None:
    """Mark all functions that is not inlined as inlined if they may be inlined due to 'max_operators' threshold."""
    functions = program.functions.values()
    non_inlined_functions = (f for f in functions if not f.is_inline)
    inlineable_functions = (
        f for f in non_inlined_functions if len(f.operators) <= max_operators
    )

    for function in inlineable_functions:
        if function.is_recursive:
            # do NOT inline functions which has self-recursion as this will lead to broken program and infinite optimizer pass.
            continue
        function.is_inline = True
