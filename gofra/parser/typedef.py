from gofra.lexer.tokens import TokenType
from gofra.parser._context import ParserContext
from gofra.parser.errors.type_definition_already_exists import (
    TypeDefinitionAlreadyExistsError,
)
from gofra.parser.type_parser import (
    consume_generic_type_parameters,
    parse_generic_type_alias_from_tokenizer,
)


def unpack_type_definition_from_token(context: ParserContext) -> None:
    name_token = context.next_token()

    if name_token.type != TokenType.IDENTIFIER:
        msg = f"Expected type definition name at {name_token.location} to be an identifier but got {name_token.type.name}"
        raise ValueError(msg)

    typename = name_token.text
    if context.get_type(typename):
        raise TypeDefinitionAlreadyExistsError(typename, name_token.location)
    generic_type_params = consume_generic_type_parameters(context)
    context.types[typename] = parse_generic_type_alias_from_tokenizer(
        context,
        generic_type_params=generic_type_params,
    )
