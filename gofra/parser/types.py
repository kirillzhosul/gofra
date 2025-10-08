from gofra.lexer.tokens import TokenType
from gofra.parser._context import ParserContext
from gofra.types import Type
from gofra.types.composite.array import ArrayType
from gofra.types.composite.pointer import PointerType
from gofra.types.registry import PRIMITIVE_TYPE_REGISTRY


def parse_type_from_text(typename: str) -> Type | None:
    # TODO(@kirillzhosul): Refactor this into proper lexer -> parser peek / consume
    if primitive_registry_type := PRIMITIVE_TYPE_REGISTRY.get(typename, None):
        return primitive_registry_type

    if typename.startswith("*"):
        points_to = parse_type_from_text(typename.removeprefix("*"))
        if not points_to:
            return None
        return PointerType(points_to)

    if "[" in typename:
        array_type = parse_type_from_text(typename.split("[")[0])
        if not array_type:
            return None
        array_size = typename.split("[", maxsplit=1)[1].removesuffix("]")

        if array_size == "" or array_size.isdigit():
            array_elements = int(array_size or "0")
            return ArrayType(element_type=array_type, elements_count=array_elements)

    return None


def parser_type_from_tokenizer(context: ParserContext) -> Type:
    # TODO(@kirillzhosul): deep pointer is not allowed
    # TODO(@kirillzhosul): distinguish array-of-pointers and pointer-to-array

    t = context.next_token()

    is_pointer = False
    if t.type == TokenType.STAR:
        is_pointer = True
        t = context.next_token()

    if t.type != TokenType.IDENTIFIER:
        msg = f"While expecting type expected identifier but got {t.type.name}"
        raise NotImplementedError(msg)

    aggregated_type: Type | None = PRIMITIVE_TYPE_REGISTRY.get(t.text, None)

    if not aggregated_type:
        msg = f"Expected primitive registry type but got {t.text}."
        raise ValueError(msg)

    if context.peek_token().type == TokenType.LBRACKET:
        _ = context.next_token()  # Consume LBRACKET

        elements = 0
        elements_or_rbracket = context.next_token()

        if elements_or_rbracket.type == TokenType.INTEGER:
            assert isinstance(elements_or_rbracket.value, int)
            elements = elements_or_rbracket.value

            rbracket = context.next_token()
            if rbracket.type != TokenType.RBRACKET:
                msg = f"Expected RBRACKET after array type elements qualifier but got {rbracket.type.name}"
                raise ValueError(msg)
        elif elements_or_rbracket.type != TokenType.RBRACKET:
            msg = f"Expected RBRACKET after array type empty qualifier but got {elements_or_rbracket.type.name}"

        aggregated_type = ArrayType(
            element_type=aggregated_type,
            elements_count=elements,
        )

    if is_pointer:
        return PointerType(points_to=aggregated_type)

    return aggregated_type
