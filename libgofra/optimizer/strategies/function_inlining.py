from __future__ import annotations

from typing import TYPE_CHECKING

from gofra.cli.output import cli_message
from libgofra.hir.function import FunctionInlineAttribute
from libgofra.hir.operator import FunctionCallOperand, Operator
from libgofra.optimizer.helpers.call_graph import CallGraph
from libgofra.parser.operators import OperatorType

if TYPE_CHECKING:
    from collections.abc import Generator

    from libgofra.hir.function import Function
    from libgofra.hir.module import Module


DEBUG_TRACE_INLINES = False


def optimize_function_inlining(
    module: Module,
    max_operators: int,
    max_iterations: int,
) -> None:
    """Optimize function inlining (mark small functions less than 'max_operators' as inline and resolve old reference as code block'."""
    cg = CallGraph(module)
    _mark_inlineable_functions_as_inline(module, cg=cg, max_operators=max_operators)

    inline_functions = [f for f in module.functions.values() if f.attrs.inline]
    pending: list[Function] = []
    for f in inline_functions:
        pending.extend(cg.get_node(f).callers)

    # TODO(@kirillzhosul): perf, possible can be optimized by using an parallel inlining as callers of inline functions are independent of each other.
    # but we need to track reference ? this is possibly make solution more complex.

    for function in pending:
        _mutate_inline_callers(
            function=function,
            module=module,
            max_iterations=max_iterations,
        )


def _mutate_inline_callers(
    function: Function,
    module: Module,
    max_iterations: int,
) -> None:
    has_rel_jumps = function.has_relative_jumps
    for _ in range(max_iterations):
        # Iterate function source until all new inlined function calls is not folded.

        # TODO(@kirillzhosul): Why exactly we do that not in a single pass?
        # and should not we mark inlineable functions again ?
        # (this must be performed once in pending run loop?)

        iteration_has_fold = False
        for idx, operator in enumerate(function.operators):
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
            if not called_function.attrs.inline:
                continue

            assert operator.type != OperatorType.PUSH_FUNCTION_POINTER, (
                "Tried to inline function pointer obtain"
            )
            if has_rel_jumps:
                # TODO(@kirillzhosul): must be resolve sorta ASAP as we can inline those functions right, but it will require relative jumps in operators and finishing inlining direct calls.
                cli_message(
                    "WARNING",
                    f"Possible partial inlining of function `{called_function.name}` defined at {called_function.defined_at}, function has been unmarked as inline!",
                )
                called_function.attrs.inline = FunctionInlineAttribute.NEVER
                continue
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
    ) -> Generator[Operator]:
        # TODO: This requires proper for example loop-unrolling but now left as is
        for operator in inlined.operators:
            if operator.jumps_to_operator_idx:
                msg = "Inlining function with jumps is not supported yet, please remove inline mark or disable inlining optimizations"
                raise NotImplementedError(msg)
            if operator.type == OperatorType.FUNCTION_RETURN:
                # Remove return operator as it is not needed inlined
                continue
            yield operator

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
        if function.attrs.inline:
            continue
        if not should_inline_function(function, cg, max_operators):
            continue

        if DEBUG_TRACE_INLINES:
            print(f"[CGO] Marked as inline: `{function.name}`")
        function.attrs.inline = FunctionInlineAttribute.ALWAYS


def should_inline_function(  # noqa: PLR0911
    function: Function,
    cg: CallGraph,
    max_operators: int,
) -> bool:
    if function.attrs.external or function.is_public:
        return False

    if function.outer_function:
        # If this is lambda we cannot inline it
        return False

    if function.attrs.inline:
        # Explicitly marked as inline (attribute) - always inline
        return True

    if function.has_relative_jumps:
        # Do not inline functions which has relative jumps as this will lead to broken program and infinite optimizer pass.
        return False

    if function.parameters or function.variables:
        # Do not inline functions which has parameters or local variables as we currently do not support expanding memory locations.
        return False

    if function.attrs.recursive:
        # do NOT inline functions which has self-recursion as this will lead to broken program and infinite optimizer pass.
        return False

    cg_node = cg.get_node(function)
    if cg_node.has_incoming_address_obtain:
        return False

    function_size = len(function.operators)
    return function_size <= max_operators
