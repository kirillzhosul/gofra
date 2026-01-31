from libgofra.lexer.tokens import Token, TokenType
from libgofra.parser._context import ParserContext
from libgofra.parser.errors.cannot_infer_var_type_from_empty_array_initializer import (
    CannotInferVariableTypeFromEmptyArrayInitializerError,
)
from libgofra.parser.errors.cannot_infer_var_type_from_initializer import (
    CannotInferVariableTypeFromInitializerError,
)
from libgofra.types._base import Type
from libgofra.types.composite.array import ArrayType
from libgofra.types.composite.pointer import PointerMemoryLocation, PointerType
from libgofra.types.composite.string import StringType
from libgofra.types.primitive.character import CharType
from libgofra.types.primitive.integers import I64Type


def infer_type_from_initializer(
    context: ParserContext,
    varname_token: Token,
) -> Type:
    """Infer which type definition must has based on upcoming initializer.

    E.g `x = ...` where cursor points at `...` peeks into initializer and guess which type it has.
    Simple case: if encountered an integer this definition must has integer type

    Used for inference of variable type when it has no explicit type

    Currently allows:
        INT -> int
        CHAR -> char
        STRING -> *str
        ARRAY<T> -> array<T[0]>
    """
    # TODO(@kirillzhosul): Allow auto inference of structure initializer?
    # TODO(@kirillzhosul): Allow casts for initializer?

    peeked = context.peek_token()
    if peeked.type == TokenType.INTEGER:
        return I64Type()

    if peeked.type == TokenType.CHARACTER:
        return CharType()

    if peeked.type == TokenType.STRING:
        return PointerType(
            points_to=StringType(),
            memory_location=PointerMemoryLocation.STATIC,
        )

    if peeked.type == TokenType.LBRACKET:
        # peek at next token after `[` and restore it
        lbracket = context.next_token()

        if context.peek_token().type == TokenType.RBRACKET:
            # Empty array initializer -> `[]`, cannot infer
            raise CannotInferVariableTypeFromEmptyArrayInitializerError(
                varname_token.text,
                varname_token.location,
            )

        # Try to infer type from first element
        element_t = infer_type_from_initializer(context, varname_token)
        context.push_token_back_upfront_peeked(lbracket)
        return ArrayType(
            element_type=element_t,
            elements_count=0,  # Incomplete array type - size must be fulfilled by initializer later
        )

    raise CannotInferVariableTypeFromInitializerError(
        varname_token.text,
        varname_token.location,
    )
