from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import MutableSequence


class SExpr:
    """S-expression builder for WAT."""

    items: "MutableSequence[object | SExpr]"

    def __init__(self, *items: "object | SExpr") -> None:
        self.items = list(items)

    def build(self) -> str:
        if not self.items:
            return "()"

        expr: list[str] = []
        for item in self.items:
            expr.extend([str(item)])

        return f"({' '.join(expr)})"

    def add_node(self, other: "object | SExpr") -> None:
        self.items.append(other)

    def __str__(self) -> str:
        return self.build()
