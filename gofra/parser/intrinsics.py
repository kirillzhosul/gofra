from enum import IntEnum, auto


class Intrinsic(IntEnum):
    INCREMENT = auto()
    DECREMENT = auto()

    PLUS = auto()
    MINUS = auto()
    MULTIPLY = auto()
    DIVIDE = auto()
    MODULUS = auto()

    EQUAL = auto()
    NOT_EQUAL = auto()
    LESS_THAN = auto()
    GREATER_THAN = auto()
    LESS_EQUAL_THAN = auto()
    GREATER_EQUAL_THAN = auto()

    MEMORY_LOAD = auto()
    MEMORY_STORE = auto()

    SYSCALL0 = auto()
    SYSCALL1 = auto()
    SYSCALL2 = auto()
    SYSCALL3 = auto()
    SYSCALL4 = auto()
    SYSCALL5 = auto()
    SYSCALL6 = auto()

    COPY = auto()
    DROP = auto()
    SWAP = auto()

    BREAKPOINT = auto()


WORD_TO_INTRINSIC = {
    "+": Intrinsic.PLUS,
    "-": Intrinsic.MINUS,
    "*": Intrinsic.MULTIPLY,
    "/": Intrinsic.DIVIDE,
    "==": Intrinsic.EQUAL,
    "!=": Intrinsic.NOT_EQUAL,
    "<": Intrinsic.LESS_THAN,
    ">": Intrinsic.GREATER_THAN,
    ">=": Intrinsic.LESS_EQUAL_THAN,
    "<=": Intrinsic.GREATER_EQUAL_THAN,
    "%": Intrinsic.MODULUS,
    "dec": Intrinsic.DECREMENT,
    "inc": Intrinsic.INCREMENT,
    "swap": Intrinsic.SWAP,
    "copy": Intrinsic.COPY,
    "drop": Intrinsic.DROP,
    "syscall0": Intrinsic.SYSCALL0,
    "syscall1": Intrinsic.SYSCALL1,
    "syscall2": Intrinsic.SYSCALL2,
    "syscall3": Intrinsic.SYSCALL3,
    "syscall4": Intrinsic.SYSCALL4,
    "syscall5": Intrinsic.SYSCALL5,
    "syscall6": Intrinsic.SYSCALL6,
    "?>": Intrinsic.MEMORY_LOAD,
    "!<": Intrinsic.MEMORY_STORE,
    "breakpoint": Intrinsic.BREAKPOINT,
}
