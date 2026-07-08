from libgofra.hir.operator import OperatorType
from libgofra.lexer.tokens import Token, TokenType
from libgofra.parser._context import ParserScope
from libgofra.typecheck.errors.user_defined_compile_time_error import (
    UserDefinedCompileTimeError,
)


def unpack_compile_time_error(context: ParserScope, token: Token) -> None:
    context.expect_token(TokenType.STRING)
    message_tok = context.next_token()
    assert isinstance(message_tok.value, str)
    if context.parent is None:
        # If global scope - emit right now
        raise UserDefinedCompileTimeError(at=token.location, message=message_tok.value)
    context.push_new_operator(
        OperatorType.COMPILE_TIME_ERROR,
        token=token,
        operand=message_tok.value,
        is_contextual=False,
    )
