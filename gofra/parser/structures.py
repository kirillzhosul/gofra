from collections.abc import Mapping
from typing import TYPE_CHECKING

from gofra.lexer.keywords import Keyword
from gofra.lexer.tokens import Token, TokenType
from gofra.parser._context import ParserContext
from gofra.parser.type_parser import (
    consume_generic_type_parameters,
    parse_concrete_type_from_tokenizer,
    parse_generic_type_alias_from_tokenizer,
)
from gofra.types.composite.structure import StructureType
from gofra.types.generics import GenericParametrizedType, GenericStructureType

if TYPE_CHECKING:
    from gofra.types._base import Type


def unpack_structure_definition_from_token(context: ParserContext) -> None:
    name_token = context.next_token()
    if name_token.type != TokenType.IDENTIFIER:
        msg = f"Expected structure name at {name_token.location} to be an identifier but got {name_token.type.name}"
        raise ValueError(msg)

    name = name_token.text

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

    _consume_concrete_structure_type_definition(context, name)


def _consume_generic_structure_type_definition(
    context: ParserContext,
    name: str,
    type_params: Mapping[str, Token],
) -> None:
    # Forward declare this struct so users may use that type in structure definition
    # this must to be back-patched after parsing types
    ref = GenericStructureType(name=name, fields={}, fields_ordering=[])
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
) -> None:
    # Forward declare this struct so users may use that type in structure definition
    # this must to be back-patched after parsing types
    ref = StructureType(
        name=name,
        fields={},
        cpu_alignment_in_bytes=8,  # assume we always on 64 bit machine (TODO)
        fields_ordering=[],
    )
    context.structs[name] = ref

    fields: dict[str, Type] = {}
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
        field_type = parse_concrete_type_from_tokenizer(context)
        fields_ordering.append(field_name)
        fields[field_name] = field_type

    # Back-patch reference
    ref.fields = fields
    ref.fields_ordering = fields_ordering
    ref.recalculate_size_in_bytes()
