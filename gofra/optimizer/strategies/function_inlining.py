from __future__ import annotations

from typing import TYPE_CHECKING

from gofra.parser.operators import OperatorType

if TYPE_CHECKING:
    from gofra.context import ProgramContext
    from gofra.parser.functions.function import Function


def optimize_function_inlining(
    program: ProgramContext,
    max_operators: int,
    max_iterations: int,
) -> None:
    """Optimize function inlining (mark small functions less than 'max_operators' as inline and resolve old reference as code block'."""
    _mark_inlineable_functions_as_inline(program, max_operators=max_operators)

    for function in (*program.functions.values(), program.entry_point):
        for _ in range(max_iterations):
            iteration_has_fold = False
            for idx, operator in enumerate(function.source):
                # Iterate each function source 'max_iterations' times until all new inlined function calls is not folded.
                if operator.type != OperatorType.FUNCTION_CALL:
                    continue
                assert isinstance(operator.operand, str)
                called_function = program.functions[operator.operand]
                if not called_function.emit_inline_body:
                    continue

                iteration_has_fold = True
                function.source = [
                    *function.source[:idx],
                    *called_function.source,
                    *function.source[idx + 1 :],
                ]

            if not iteration_has_fold:
                break


def _mark_inlineable_functions_as_inline(
    program: ProgramContext,
    max_operators: int,
) -> None:
    """Mark all functions that is not inlined as inlined if they may be inlined due to 'max_operators' threshold."""
    functions = program.functions.values()
    non_inlined_functions = (f for f in functions if not f.emit_inline_body)
    inlineable_functions = (
        f for f in non_inlined_functions if len(f.source) <= max_operators
    )

    for function in inlineable_functions:
        if _is_function_has_recursion(function):
            # do NOT inline functions which has self-recursion as this will lead to broken program and infinite optimizer pass.
            continue
        function.emit_inline_body = True


def _is_function_has_recursion(function: Function) -> bool:
    """Check is given function has self-recursion."""
    return any(
        operator.type == OperatorType.FUNCTION_CALL
        and operator.operand == function.name
        for operator in function.source
    )
