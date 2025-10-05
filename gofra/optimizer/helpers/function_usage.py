from collections.abc import Iterable
from itertools import chain

from gofra.context import ProgramContext
from gofra.parser.functions.function import Function
from gofra.parser.operators import OperatorType


def is_function_has_callers(program: ProgramContext, function_name: str) -> bool:
    """Check is given function was called at least once in whole program."""
    assert function_name in program.functions, (
        "Expected existing function in `is_function_has_callers`"
    )

    function = program.functions[function_name]
    return any(
        operator.type == OperatorType.FUNCTION_CALL
        and operator.operand == function.name
        for operator in chain.from_iterable(
            (f.source for f in (*program.functions.values(), program.entry_point)),
        )
    )


def search_unused_functions(program: ProgramContext) -> Iterable[Function]:
    """Search unused functions without any usage (excluding global function symbols)."""
    return [
        f
        for f in program.functions.values()
        if not f.is_global_linker_symbol
        and not is_function_has_callers(program, f.name)
    ]
