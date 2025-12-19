from libgofra.hir.operator import OperatorType
from libgofra.lexer.tokens import Token
from libgofra.parser._context import ParserContext
from libgofra.parser.type_parser import (
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
