from typing import TYPE_CHECKING

from gofra.lexer.keywords import Keyword
from gofra.lexer.tokens import TokenType
from gofra.parser._context import ParserContext
from gofra.parser.types import parser_type_from_tokenizer
from gofra.types.composite.structure import StructureType

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
        field_type = parser_type_from_tokenizer(context)
        fields_ordering.append(field_name)
        fields[field_name] = field_type

    # Back-patch reference
    ref.fields = fields
    ref.fields_ordering = fields_ordering
    ref.recalculate_size_in_bytes()
