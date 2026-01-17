"""Static analysis* functions.

Emits warning if they succeed to find some possible errors and bad things
"""

from collections.abc import Callable, Mapping, MutableMapping
from copy import deepcopy

from libgofra.hir.function import Function
from libgofra.hir.initializer import VariableIntArrayInitializerValue
from libgofra.hir.variable import Variable
from libgofra.lexer.tokens import TokenLocation
from libgofra.types._base import Type
from libgofra.types.comparison import is_types_same
from libgofra.types.composite.array import ArrayType
from libgofra.types.composite.pointer import PointerMemoryLocation, PointerType
from libgofra.types.composite.structure import StructureType
from libgofra.types.reordering import reorder_type_fields


def lint_structure_types(
    on_lint_warning: Callable[[str], None],
    structures: MutableMapping[str, StructureType],
) -> None:
    for struct in structures.values():
        if struct.is_reordering_allowed or struct.is_packed:
            continue
        new_order, has_possible_reorder = reorder_type_fields(
            unordered=struct.natural_order,
            fields=struct.natural_fields,
        )
        if not has_possible_reorder:
            continue

        copy = deepcopy(struct)
        copy.backpatch(fields=struct.natural_fields, order=new_order)

        diff = struct.size_in_bytes - copy.size_in_bytes
        if diff <= 0:
            # TODO(@kirillzhosul): Why diff is zero while reordering is applied -> should be removed from reorder_type_fields?
            continue
        on_lint_warning(
            f"Struct {struct.name} has possible reordering! Padding on current order consumes additional {diff} bytes! ({struct.size_in_bytes}b unordered, {copy.size_in_bytes}b reordered), add `reorder` attribute",
        )


def lint_variables_initializer(
    on_lint_warning: Callable[[str], None],
    variables: MutableMapping[str, Variable[Type]],
) -> None:
    for v in variables.values():
        if not isinstance(v.type, ArrayType) or not isinstance(
            v.initial_value,
            VariableIntArrayInitializerValue,
        ):
            continue
        if v.initial_value.default == 0:
            continue
        if (v.type.elements_count - len(v.initial_value.values)) != 0:
            continue

        on_lint_warning(
            f"Redundant array initializer filler for {v.name} defined at {v.defined_at}, array is already fulfilled, either remove it or expand array",
        )


def lint_stack_memory_retval(
    on_lint_warning: Callable[[str], None],
    function: Function,
    retval_t: Type,
) -> None:
    """Emit lint warning if returned type is an stack memory."""
    if not isinstance(retval_t, PointerType):
        return
    if retval_t.memory_location == PointerMemoryLocation.STACK:
        on_lint_warning(
            f"""Returning an pointer from function that has stack memory location inside function '{function.name}' defined at {function.defined_at}!""",
        )


def lint_typecast_same_type(
    on_lint_warning: Callable[[str], None],
    t_from: Type,
    t_to: Type,
    at: TokenLocation,
) -> None:
    """Emit lint warning if casting one type to the same type."""
    if is_types_same(t_from, t_to, strategy="strict-same-type"):
        on_lint_warning(
            f"Redundant static type cast from `{t_from}` to `{t_to}` at {at} (e.g type is strictly same so it is considered as redundant)",
        )


def lint_unused_function_local_variables(
    on_lint_warning: Callable[[str], None],
    function: Function,
    references_variables: Mapping[str, Variable[Type]],
) -> None:
    func_vars = set(function.variables.keys())
    ref_vars = set(references_variables.keys())
    unused_variables = func_vars.difference(ref_vars)
    for varname in unused_variables:
        var = function.variables[varname]
        on_lint_warning(
            f"Unused function variable '{varname}' declared at {var.defined_at}, either remove it or use it",
        )


def emit_no_return_attribute_propagation_warning(
    on_lint_warning: Callable[[str], None],
    function: Function,
) -> None:
    on_lint_warning(
        f"Function '{function.name}' defined at {function.defined_at} calls to no-return function inside no conditional blocks, consider propagate no-return attribute",
    )


def emit_unreachable_code_after_early_return_warning(
    on_lint_warning: Callable[[str], None],
    function: Function,
    return_at: TokenLocation,
    unreachable_at: TokenLocation,
) -> None:
    on_lint_warning(
        f"Function '{function.name}' has operators after early-return at {return_at}! This is unreachable code starting at {unreachable_at}!",
    )


def emit_unused_global_variable_warning(
    on_lint_warning: Callable[[str], None],
    variable: Variable[Type],
) -> None:
    on_lint_warning(
        f"Unused non-constant global variable '{variable.name}' defined at {variable.defined_at}",
    )


def emit_unreachable_code_after_no_return_call_warning(
    on_lint_warning: Callable[[str], None],
    call_from: Function,
    call_at: TokenLocation,
    callee: Function,
    unreachable_at: TokenLocation,
) -> None:
    assert callee.is_no_return
    on_lint_warning(
        f"Function '{call_from.name}' has operators after calling no-return function '{callee.name}' at {call_at}! This is unreachable code starting at {unreachable_at}!",
    )
