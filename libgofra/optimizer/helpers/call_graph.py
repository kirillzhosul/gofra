from collections.abc import Generator, Iterable, MutableMapping, MutableSequence
from dataclasses import dataclass, field

from libgofra.hir.function import Function
from libgofra.hir.module import Module
from libgofra.hir.operator import FunctionCallOperand, Operator, OperatorType


@dataclass
class CallSite:
    """Represents a specific location where a function is called/reference obtained."""

    # Who is calling
    caller: Function

    # Who is called
    callee: Function

    # HIR operator (FUNCTION_CALL, PUSH_FUNCTION_POINTER)
    instruction: Operator

    # Index of instruction within caller instruction set
    instruction_idx: int

    @property
    def is_direct_call(self) -> bool:
        """True when call is direct call to desired callee."""
        return self.instruction.type == OperatorType.FUNCTION_CALL

    @property
    def is_address_obtain(self) -> bool:
        """True when call site references taking address of that function."""
        return self.instruction.type == OperatorType.PUSH_FUNCTION_POINTER


@dataclass
class CallGraphNode:
    # Unique node identifier - an function which it holds
    function: Function

    # Node edges (caller, callee sites)
    incoming_edges: MutableSequence[CallSite] = field()
    outgoing_edges: MutableSequence[CallSite] = field()

    @property
    def has_incoming_direct_calls(self) -> bool:
        return any(edge.is_direct_call for edge in self.incoming_edges)

    @property
    def has_incoming_address_obtain(self) -> bool:
        return any(edge.is_address_obtain for edge in self.incoming_edges)

    @property
    def callers(self) -> Iterable[Function]:
        """Get callers of this function node from incoming edges."""
        return [edge.caller for edge in self.incoming_edges]

    @property
    def callees(self) -> Iterable[Function]:
        """Get functions this function calls to from incoming edges."""
        return [edge.callee for edge in self.outgoing_edges]


class CallGraph:
    """Graph of every function in module and corresponding calls as edges."""

    _nodes: MutableMapping[Function, CallGraphNode]

    def __init__(self, module: Module) -> None:
        self.module = module

        self._nodes = self._get_default_node_graph()
        self._analyze_calls()

    def get_node(self, function: Function) -> CallGraphNode:
        return self._nodes[function]

    def get_root_functions(self) -> Iterable[Function]:
        """Get root node functions which has no callers."""
        return (node.function for node in self._nodes.values() if not node.callers)

    ### Internal implementation

    def _get_default_node_graph(self) -> dict[Function, CallGraphNode]:
        """Fulfill nodes with their default nodes variant."""
        return {
            function: CallGraphNode(
                function,
                incoming_edges=[],
                outgoing_edges=[],
            )
            for function in self.module.functions.values()
        }

    def _analyze_calls(self) -> None:
        """Traverse module functions and build whole call graph on it."""
        for caller in self.module.functions.values():
            for call_site in self._get_function_underlying_call_sites(caller):
                self.get_node(call_site.caller).outgoing_edges.append(call_site)
                self.get_node(call_site.callee).incoming_edges.append(call_site)

    def _get_function_underlying_call_sites(
        self,
        caller: Function,
    ) -> Generator[CallSite]:
        for idx, operator in enumerate(caller.operators):
            if (calee := self._get_operator_callee_if_call(operator)) is None:
                continue
            yield CallSite(
                caller=caller,
                callee=calee,
                instruction=operator,
                instruction_idx=idx,
            )

    def _get_operator_callee_if_call(self, operator: Operator) -> Function | None:
        if operator.type not in (
            OperatorType.FUNCTION_CALL,
            OperatorType.PUSH_FUNCTION_POINTER,
        ):
            return None
        assert isinstance(operator.operand, FunctionCallOperand)
        callee = self.module.resolve_function_dependency(
            operator.operand.module,
            operator.operand.get_name(),
        )

        if not callee:
            msg = f"Missing mod dependency for DCE, possible DCE removed existed function call without DCE propagation {operator.operand}"
            raise ValueError(msg)

        return callee
