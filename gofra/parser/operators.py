from __future__ import annotations

from gofra.hir.operator import OperatorType

IDENTIFIER_TO_OPERATOR_TYPE = {
    "+": OperatorType.ARITHMETIC_PLUS,
    "-": OperatorType.ARITHMETIC_MINUS,
    "*": OperatorType.ARITHMETIC_MULTIPLY,
    "/": OperatorType.ARITHMETIC_DIVIDE,
    "%": OperatorType.ARITHMETIC_MODULUS,
    "<": OperatorType.COMPARE_LESS,
    ">": OperatorType.COMPARE_GREATER,
    "==": OperatorType.COMPARE_EQUALS,
    "!=": OperatorType.COMPARE_NOT_EQUALS,
    "<=": OperatorType.COMPARE_LESS_EQUALS,
    ">=": OperatorType.COMPARE_GREATER_EQUALS,
    "||": OperatorType.LOGICAL_OR,
    "&&": OperatorType.LOGICAL_AND,
    ">>": OperatorType.SHIFT_RIGHT,
    "<<": OperatorType.SHIFT_LEFT,
    "|": OperatorType.BITWISE_OR,
    "&": OperatorType.BITWISE_AND,
    "^": OperatorType.BITWISE_XOR,
    "?>": OperatorType.MEMORY_VARIABLE_READ,
    "!<": OperatorType.MEMORY_VARIABLE_WRITE,
}
