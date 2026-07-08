from libgofra.lexer import Token
from libgofra.parser._context import ParserScope
from libgofra.parser.operators import IDENTIFIER_TO_OPERATOR_TYPE, OperatorType


def push_string_operator(context: ParserScope, token: Token) -> None:
    assert isinstance(token.value, str)
    context.push_new_operator(
        type=OperatorType.PUSH_STRING,
        token=token,
        operand=token.value,
    )


def push_integer_operator(context: ParserScope, token: Token) -> None:
    assert isinstance(token.value, int)
    context.push_new_operator(
        type=OperatorType.PUSH_INTEGER,
        token=token,
        operand=token.value,
    )


def push_float_operator(context: ParserScope, token: Token) -> None:
    assert isinstance(token.value, float)
    context.push_new_operator(
        type=OperatorType.PUSH_FLOAT,
        token=token,
        operand=token.value,
    )


def try_push_intrinsic_operator(context: ParserScope, token: Token) -> bool:
    assert isinstance(token.value, str)

    operator_type = IDENTIFIER_TO_OPERATOR_TYPE.get(token.value)
    if operator_type:
        context.push_new_operator(type=operator_type, token=token)
        return True

    return False
