from collections.abc import Iterable
from itertools import chain

from libgofra.hir.function import Function
from libgofra.hir.module import Module
from libgofra.hir.operator import FunctionCallOperand, Operator
from libgofra.parser.operators import OperatorType


def is_function_has_callers(program: Module, function_name: str) -> bool:
    """Check is given function was called at least once in whole program."""
    assert function_name in program.functions, (
        "Expected existing function in `is_function_has_callers`"
    )

    return any(
        _is_call_operator(operator, function_name)
        for operator in chain.from_iterable(
            (f.operators for f in program.functions.values() if not f.is_leaf),
        )
    )


def _is_call_operator(operator: Operator, callee: str) -> bool:
    if operator.type != OperatorType.FUNCTION_CALL:
        return False
    assert isinstance(operator.operand, FunctionCallOperand)
    return operator.operand.func_name == callee


def search_unused_functions(program: Module) -> Iterable[Function]:
    """Search unused functions without any usage (excluding global function symbols)."""
    return [
        f
        for f in program.functions.values()
        if not f.is_public
        and not f.is_external
        and not is_function_has_callers(program, f.name)
    ]
