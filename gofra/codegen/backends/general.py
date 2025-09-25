"""General consts and types for registers and architecture (including FFI/ABI/IPC)."""

from typing import Literal

from gofra.parser.intrinsics import Intrinsic

CODEGEN_ENTRY_POINT_SYMBOL = "_start"
CODEGEN_GOFRA_CONTEXT_LABEL = ".L_%s_%s"

type CODEGEN_GOFRA_ON_STACK_OPERATIONS = Literal[
    "+",
    "-",
    "*",
    "//",
    "%",
    ">",
    ">=",
    "<",
    "<=",
    "==",
    "!=",
    "++",
    "--",
    "||",
    "&&",
    "&",
    "|",
]

CODEGEN_INTRINSIC_TO_ASSEMBLY_OPS: dict[
    Intrinsic,
    CODEGEN_GOFRA_ON_STACK_OPERATIONS,
] = {
    Intrinsic.PLUS: "+",
    Intrinsic.MINUS: "-",
    Intrinsic.MULTIPLY: "*",
    Intrinsic.DIVIDE: "//",
    Intrinsic.MODULUS: "%",
    Intrinsic.INCREMENT: "++",
    Intrinsic.DECREMENT: "--",
    Intrinsic.NOT_EQUAL: "!=",
    Intrinsic.GREATER_EQUAL_THAN: ">=",
    Intrinsic.LESS_EQUAL_THAN: "<=",
    Intrinsic.LESS_THAN: "<",
    Intrinsic.GREATER_THAN: ">",
    Intrinsic.EQUAL: "==",
    Intrinsic.LOGICAL_OR: "||",
    Intrinsic.LOGICAL_AND: "&&",
    Intrinsic.BITWISE_OR: "|",
    Intrinsic.BITWISE_AND: "&",
}
