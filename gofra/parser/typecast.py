from gofra.hir.operator import OperatorType
from gofra.lexer.tokens import Token
from gofra.parser._context import ParserContext
from gofra.parser.types import (
    parse_concrete_type_from_tokenizer,
)


def unpack_typecast_from_token(context: ParserContext, typecast_token: Token) -> None:
    typename = parse_concrete_type_from_tokenizer(context)

    context.push_new_operator(
        OperatorType.STATIC_TYPE_CAST,
        typecast_token,
        typename,
        is_contextual=False,
    )
