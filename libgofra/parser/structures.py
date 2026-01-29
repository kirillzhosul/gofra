from collections.abc import Mapping
from typing import TYPE_CHECKING

from libgofra.exceptions import GofraError
from libgofra.lexer.keywords import Keyword
from libgofra.lexer.tokens import Token, TokenType
from libgofra.parser._context import ParserContext
from libgofra.parser.errors.wildcard_cannot_be_used_as_symbol_name import (
    WildcardCannotBeUsedAsSymbolNameError,
)
from libgofra.parser.type_parser import (
    consume_generic_type_parameters,
    parse_concrete_type_from_tokenizer,
    parse_generic_type_alias_from_tokenizer,
)
from libgofra.types.composite.structure import StructureType
from libgofra.types.generics import GenericParametrizedType, GenericStructureType

if TYPE_CHECKING:
    from libgofra.types._base import Type


def unpack_structure_definition_from_token(context: ParserContext) -> None:
    attr_is_packed, attr_reorder = _consume_structure_attributes(context)

    name_token = context.next_token()
    if name_token.type != TokenType.IDENTIFIER:
        msg = f"Expected structure name at {name_token.location} to be an identifier but got {name_token.type.name}"
        raise ValueError(msg)

    name = name_token.text
    if name == "_":
        raise WildcardCannotBeUsedAsSymbolNameError(at=name_token.location)

    if context.name_is_already_taken(name):
        msg = f"Structure name {name} is already taken by other definition"
        raise ValueError(msg)
    if (
        context.peek_token().type == TokenType.LCURLY
        and not context.peek_token().has_trailing_whitespace
    ):
        type_params = consume_generic_type_parameters(context)
        _consume_generic_structure_type_definition(
            context,
            name,
            type_params=type_params,
        )
        return

    _consume_concrete_structure_type_definition(
        context,
        name,
        attr_is_packed=attr_is_packed,
        attr_reorder=attr_reorder,
    )


def _consume_structure_attributes(context: ParserContext) -> tuple[bool, bool]:
    attr_is_packed, attr_reorder = False, False

    while context.peek_token().type == TokenType.KEYWORD:
        attr_token = context.next_token()
        assert attr_token.type == TokenType.KEYWORD
        match attr_token.value:
            case Keyword.ATTR_STRUCT_PACKED:
                assert not attr_is_packed, attr_token.location
                attr_is_packed = True
            case Keyword.ATTR_STRUCT_REORDER:
                assert not attr_reorder, attr_token.location
                attr_reorder = True
            case _:
                raise ValueError(attr_token)

    return attr_is_packed, attr_reorder


def _consume_generic_structure_type_definition(
    context: ParserContext,
    name: str,
    type_params: Mapping[str, Token],
) -> None:
    # Forward declare this struct so users may use that type in structure definition
    # this must to be back-patched after parsing types
    attr_is_packed, attr_reorder = _consume_structure_attributes(context)

    ref = GenericStructureType(
        name=name,
        fields={},
        fields_ordering=[],
        is_packed=attr_is_packed,
        reorder=attr_reorder,
    )
    context.types[name] = (
        ref  # TODO(@kirillzhosul): Codebase is a mess with these type/structure containers - can be single one ?
    )

    fields: dict[str, Type | GenericParametrizedType] = {}
    fields_ordering: list[str] = []

    while token := context.next_token():
        if token.type == TokenType.KEYWORD and token.value == Keyword.END:
            # End of structure block definition
            break
        field_name_token = token

        if field_name_token.type != TokenType.IDENTIFIER:
            msg = f"Expected structure field name at {field_name_token.location} to be an identifier but got {field_name_token.type.name}"
            raise ValueError(msg)
        field_name = field_name_token.text
        field_type = parse_generic_type_alias_from_tokenizer(
            context,
            generic_type_params=type_params,
        )
        fields_ordering.append(field_name)
        fields[field_name] = field_type

    # Back-patch reference
    ref.fields = fields
    ref.fields_ordering = fields_ordering


def _consume_concrete_structure_type_definition(
    context: ParserContext,
    name: str,
    *,
    attr_is_packed: bool,
    attr_reorder: bool,
) -> None:
    # Forward declare this struct so users may use that type in structure definition
    # this must to be back-patched after parsing types
    ref = StructureType(
        name=name,
        fields={},
        order=[],
        is_packed=attr_is_packed,
        reorder=attr_reorder,
    )
    context.structs[name] = ref

    fields: dict[str, Type] = {}
    fields_ordering: list[str] = []

    has_forward_reference = False
    while token := context.next_token():
        if token.type == TokenType.KEYWORD and token.value == Keyword.END:
            # End of structure block definition
            break
        field_name_token = token

        if field_name_token.type != TokenType.IDENTIFIER:
            msg = f"Expected structure field name at {field_name_token.location} to be an identifier but got {field_name_token.type.name}"
            raise ValueError(msg)
        field_name = field_name_token.text
        field_type = parse_concrete_type_from_tokenizer(context)
        if id(field_type) == id(ref):
            has_forward_reference = True
        fields_ordering.append(field_name)
        fields[field_name] = field_type

    # Back-patch reference
    ref.backpatch(
        fields=fields,
        order=fields_ordering,
        # TODO: proper backpatch
        has_forward_reference=has_forward_reference,
    )

    if not ref.natural_fields:
        msg = f"Structure {ref.name} has no fields."
        raise GofraError(msg)

    if ref.size_in_bytes <= 0:
        msg = f"Structure {ref} (defined around {context.peek_token().location} has zero size which is prohibited, if you define self-reference type, this leaded to infinite size (0 == inf in type)."
        raise GofraError(msg)
