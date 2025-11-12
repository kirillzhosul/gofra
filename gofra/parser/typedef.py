from gofra.lexer.tokens import TokenType
from gofra.parser._context import ParserContext
from gofra.parser.errors.type_definition_already_exists import (
    TypeDefinitionAlreadyExistsError,
)
from gofra.parser.types import parser_type_from_tokenizer


def unpack_type_definition_from_token(context: ParserContext) -> None:
    name_token = context.next_token()

    if name_token.type != TokenType.IDENTIFIER:
        msg = f"Expected type definition name at {name_token.location} to be an identifier but got {name_token.type.name}"
        raise ValueError(msg)

    typename = name_token.text
    if typename in context.types:
        raise TypeDefinitionAlreadyExistsError(typename, name_token.location)
    context.types[typename] = parser_type_from_tokenizer(context)
