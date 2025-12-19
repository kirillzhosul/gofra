from collections.abc import Iterable
from itertools import chain

from libgofra.hir.function import Function
from libgofra.hir.module import Module
from libgofra.parser.operators import OperatorType


def is_function_has_callers(program: Module, function_name: str) -> bool:
    """Check is given function was called at least once in whole program."""
    assert function_name in program.functions, (
        "Expected existing function in `is_function_has_callers`"
    )

    function = program.functions[function_name]

    return any(
        operator.type == OperatorType.FUNCTION_CALL
        and operator.operand == function.name
        for operator in chain.from_iterable(
            (f.operators for f in program.functions.values() if not f.is_leaf),
        )
    )


def search_unused_functions(program: Module) -> Iterable[Function]:
    """Search unused functions without any usage (excluding global function symbols)."""
    return [
        f
        for f in program.functions.values()
        if not f.is_global and not is_function_has_callers(program, f.name)
    ]
