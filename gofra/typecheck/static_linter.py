"""Static analysis* functions.

Emits warning if they succeed to find some possible errors and bad things
"""

from collections.abc import Mapping

from gofra.cli.output import cli_linter_warning
from gofra.hir.function import Function
from gofra.hir.variable import Variable
from gofra.lexer.tokens import TokenLocation
from gofra.types._base import Type
from gofra.types.comparison import is_types_same
from gofra.types.composite.pointer import PointerMemoryLocation, PointerType


def lint_stack_memory_retval(function: Function, retval_t: Type) -> None:
    """Emit lint warning if returned type is an stack memory."""
    if not isinstance(retval_t, PointerType):
        return
    if retval_t.memory_location == PointerMemoryLocation.STACK:
        cli_linter_warning(
            f"""Returning an pointer from function that has stack memory location inside function '{function.name}' defined at {function.defined_at}!""",
        )


def lint_typecast_same_type(t_from: Type, t_to: Type, at: TokenLocation) -> None:
    """Emit lint warning if casting one type to the same type."""
    if is_types_same(t_from, t_to, strategy="strict-same-type"):
        cli_linter_warning(
            f"Redundant static type cast from `{t_from}` to `{t_to}` at {at} (e.g type is strictly same so it is considered as redundant)",
        )


def lint_unused_function_local_variables(
    function: Function,
    references_variables: Mapping[str, Variable],
) -> None:
    func_vars = set(function.variables.keys())
    ref_vars = set(references_variables.keys())
    unused_variables = func_vars.difference(ref_vars)
    for varname in unused_variables:
        var = function.variables[varname]
        cli_linter_warning(
            f"Unused function variable '{varname}' declared at {var.defined_at}, either remove it or use it",
        )
