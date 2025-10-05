from collections import deque
from collections.abc import Sequence

from gofra.types import Type


class TypeStack:
    """Stack that contains types."""

    # LIFO container structure with types
    _stack: deque[Type]

    def __init__(self, initial: Sequence[Type]) -> None:
        self._stack = deque(initial)

    def push(self, *types: Type) -> None:
        """Push arbitrary amount of types on stack."""
        self._stack.extend(types)

    def pop(self) -> Type:
        """Pop last pushed type from the stack."""
        return self._stack.pop()

    def __len__(self) -> int:
        """Get length of the stack."""
        return len(self._stack)
