from __future__ import annotations

from typing import TYPE_CHECKING

from libgofra.hir.operator import FunctionCallOperand, Operator
from libgofra.optimizer.helpers.call_graph import CallGraph
from libgofra.parser.operators import OperatorType

if TYPE_CHECKING:
    from collections.abc import Sequence

    from libgofra.hir.function import Function
    from libgofra.hir.module import Module


DEBUG_TRACE_INLINES = True


def optimize_function_inlining(
    module: Module,
    max_operators: int,
    max_iterations: int,
) -> None:
    """Optimize function inlining (mark small functions less than 'max_operators' as inline and resolve old reference as code block'."""
    cg = CallGraph(module)
    _mark_inlineable_functions_as_inline(module, cg=cg, max_operators=max_operators)

    inline_functions = [f for f in module.functions.values() if f.is_inline]
    pending: list[Function] = []
    for f in inline_functions:
        pending.extend(cg.get_node(f).callers)

    for function in pending:
        for _ in range(max_iterations):
            iteration_has_fold = False
            for idx, operator in enumerate(function.operators):
                # Iterate each function source 'max_iterations' times until all new inlined function calls is not folded.
                if operator.type not in (
                    OperatorType.FUNCTION_CALL,
                    OperatorType.PUSH_FUNCTION_POINTER,
                ):
                    continue
                assert isinstance(operator.operand, FunctionCallOperand)
                called_function = module.resolve_function_dependency(
                    operator.operand.module,
                    operator.operand.get_name(),
                )
                assert called_function
                if not called_function.is_inline:
                    continue

                assert operator.type != OperatorType.PUSH_FUNCTION_POINTER, (
                    "Tried to inline function pointer obtain"
                )
                iteration_has_fold = True
                _inline_direct_call(
                    function,
                    inline_direct_call_idx=idx,
                    inline_target=called_function,
                )

            if not iteration_has_fold:
                break


def _inline_direct_call(
    caller: Function,
    inline_direct_call_idx: int,
    inline_target: Function,
) -> None:
    def adapt_function_for_inline_expansion(
        inlined: Function,
    ) -> Sequence[Operator]:
        # TODO: This requires proper for example loop-unrolling but now left as is
        return inlined.operators

    caller.operators = [
        *caller.operators[:inline_direct_call_idx],
        *adapt_function_for_inline_expansion(inline_target),
        *caller.operators[inline_direct_call_idx + 1 :],
    ]


def _mark_inlineable_functions_as_inline(
    program: Module,
    cg: CallGraph,
    max_operators: int,
) -> None:
    """Mark all functions that is not inlined as inlined if they may be inlined due to 'max_operators' threshold."""
    for function in program.functions.values():
        if function.is_inline:
            continue
        if not should_inline_function(function, cg, max_operators):
            continue

        if DEBUG_TRACE_INLINES:
            print(f"[CGO] Marked as inline: `{function.name}`")
        function.is_inline = True


def should_inline_function(
    function: Function,
    cg: CallGraph,
    max_operators: int,
) -> bool:
    if function.is_external or function.is_public:
        return False

    if function.enclosed_in_parent:
        # If this is lambda we cannot inline it
        return False

    if function.is_inline:
        # Explicitly marked as inline (attribute) - always inline
        return True

    if function.is_recursive:
        # do NOT inline functions which has self-recursion as this will lead to broken program and infinite optimizer pass.
        return False

    cg_node = cg.get_node(function)
    if cg_node.has_incoming_address_obtain:
        return False

    function_size = len(function.operators)
    return function_size <= max_operators
