from gofra.lexer.tokens import TokenType
from gofra.parser._context import ParserContext
from gofra.parser.errors.unknown_primitive_type import UnknownPrimitiveTypeError
from gofra.types import Type
from gofra.types.composite.array import ArrayType
from gofra.types.composite.pointer import PointerType


def parser_type_from_tokenizer(
    context: ParserContext,
    *,
    allow_inferring_variable_types: bool = False,
) -> Type:
    # TODO(@kirillzhosul): deep pointer is not allowed
    # TODO(@kirillzhosul): distinguish array-of-pointers and pointer-to-array
    # TODO(@kirillzhosul): Type parsing is weird (especially new allow_inferring_variable_types) must be separated in complex-type parsing system ?

    if context.peek_token().type == TokenType.STAR:
        _ = context.next_token()  # Consume
        return PointerType(
            points_to=parser_type_from_tokenizer(
                context,
                allow_inferring_variable_types=False,
            ),
        )

    context.expect_token(TokenType.IDENTIFIER)
    t = context.next_token()

    aggregated_type: Type | None = context.get_type(t.text)
    if not aggregated_type:
        # Unable to get from primitive registry - probably an structure type definition
        aggregated_type = context.get_struct(t.text)

    if allow_inferring_variable_types and not aggregated_type:
        variable = context.search_variable_in_context_parents(t.text)
        if variable:
            aggregated_type = variable.type

    if not aggregated_type:
        raise UnknownPrimitiveTypeError(t.text, t.location)

    if context.peek_token().type == TokenType.LBRACKET:
        _ = context.next_token()  # Consume LBRACKET

        elements = 0
        elements_or_rbracket = context.next_token()

        if elements_or_rbracket.type == TokenType.INTEGER:
            assert isinstance(elements_or_rbracket.value, int)
            elements = elements_or_rbracket.value

            rbracket = context.next_token()
            if rbracket.type != TokenType.RBRACKET:
                msg = f"Expected RBRACKET after array type elements qualifier but got {rbracket.type.name} at {rbracket.location}"
                raise ValueError(msg)
        elif elements_or_rbracket.type != TokenType.RBRACKET:
            msg = f"Expected RBRACKET after array type empty qualifier but got {elements_or_rbracket.type.name}"

        aggregated_type = ArrayType(
            element_type=aggregated_type,
            elements_count=elements,
        )

    return aggregated_type
