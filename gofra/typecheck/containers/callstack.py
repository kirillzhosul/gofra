from collections import deque

from gofra.lexer.tokens import TokenLocation
from gofra.parser.functions.function import Function

type CALL = tuple[Function, TokenLocation]


class CallStack:
    """Stack that contains types at emulated types runtime."""

    # LIFO container structure with calls location
    _stack: deque[CALL]

    def __init__(self) -> None:
        self._stack = deque()

    def push(self, callee: Function, at: TokenLocation) -> None:
        """Push arbitrary amount of types on stack."""
        self._stack.append((callee, at))

    def pop(self) -> CALL:
        """Pop last pushed type from the stack."""
        return self._stack.pop()

    def __len__(self) -> int:
        """Get length of the stack."""
        return len(self._stack)

    def __repr__(self) -> str:
        return ", ".join([f.name + " " + repr(at) for f, at in self._stack])
