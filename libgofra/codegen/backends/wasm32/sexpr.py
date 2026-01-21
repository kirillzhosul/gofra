from collections.abc import Iterable
from typing import TYPE_CHECKING

from libgofra.codegen.backends.wasm32.types import WASM_TYPE

if TYPE_CHECKING:
    from collections.abc import MutableSequence

NEWLINE_SPEC = "\n"


class SExpr:
    """S-expression builder for WAT."""

    items: "MutableSequence[object | SExpr]"

    def __init__(self, *items: "object | SExpr", finite_stmt: bool = False) -> None:
        self.items = list(items)
        self.finite_stmt = finite_stmt

    def build(self) -> str:
        if not self.items:
            return "()"

        expr: list[str] = []
        for item in self.items:
            expr.extend([str(item)])

        s = f"({' '.join(expr)})"
        if self.finite_stmt:
            s += "\n"
        return s

    def __repr__(self) -> str:
        return f"SExpr({self.items})"

    def add_node(self, other: "object | SExpr") -> None:
        self.items.append(other)

    def add_nodes(self, other: "Iterable[object | SExpr]") -> None:
        self.items.extend(other)

    def __str__(self) -> str:
        return self.build()


class ImportNode(SExpr):
    """Import specified declaration from desired module."""

    def __init__(self, module: str, item: str, child: SExpr) -> None:
        super().__init__("import", f'"{module}"', f'"{item}"', child, finite_stmt=True)


class MemoryNode(SExpr):
    def __init__(self, min_pages: int = 1) -> None:
        super().__init__("memory", min_pages)


class ParamNode(SExpr):
    def __init__(self, param_types: Iterable[WASM_TYPE]) -> None:
        super().__init__("param", *param_types)


class ExportNode(SExpr):
    def __init__(self, name: str) -> None:
        super().__init__("export", f'"{name}"')


class ResultNode(SExpr):
    def __init__(self, result_type: WASM_TYPE) -> None:
        super().__init__("result", result_type)


class FunctionNode(SExpr):
    def __init__(self, name: str) -> None:
        super().__init__("func", f"${name}")


class I64ConstNode(SExpr):
    def __init__(self, value: int) -> None:
        super().__init__("i64.const", value)


class GlobalSymbolNode(SExpr):
    def __init__(
        self,
        name: str,
        store_type: WASM_TYPE,
        initializer: I64ConstNode,
        *,
        is_mutable: bool,
    ) -> None:
        type_node = SExpr("mut", store_type) if is_mutable else store_type
        super().__init__("global", f"${name}", type_node, initializer, finite_stmt=True)


class InstructionsNode(SExpr):
    def __init__(self, *items: object | SExpr, finite_stmt: bool = True) -> None:
        super().__init__(*items, finite_stmt=finite_stmt)


class InstructionNode(SExpr): ...


class ModuleNode(SExpr):
    def __init__(self) -> None:
        super().__init__("module", NEWLINE_SPEC)


class DataNode(SExpr):
    def __init__(
        self,
        offset: int,
        value: str,
    ) -> None:
        super().__init__(
            "data",
            SExpr("i32.const", offset),
            f'"{value}"',
            finite_stmt=True,
        )


class InstructionCallNode(InstructionNode):
    def __init__(self, func: str) -> None:
        super().__init__("call", f"${func}")


class CommentNode(InstructionNode):
    comment: object

    def __init__(self, comment: object) -> None:
        self.comment = comment
        self.items = []

    def build(self) -> str:
        return f";; {self.comment}"


class BlockNode(InstructionNode):
    def __init__(
        self,
        *items: object | SExpr,
        name: str,
        finite_stmt: bool = False,
    ) -> None:
        super().__init__("block", f"${name}", *items, finite_stmt=finite_stmt)


class BlockLoopNode(InstructionNode):
    def __init__(
        self,
        name: str,
    ) -> None:
        super().__init__("loop", f"${name}", finite_stmt=False)


class ThenBlockNode(InstructionNode):
    def __init__(self) -> None:
        super().__init__("then")


class IfThenBlockNode(InstructionNode):
    then_branch_ref: ThenBlockNode

    def __init__(self) -> None:
        self.then_branch_ref = ThenBlockNode()
        super().__init__("if", self.then_branch_ref)
