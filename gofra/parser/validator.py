"""Entry point validator.

Probably should not be here (in parser)
"""

from gofra.consts import GOFRA_ENTRY_POINT
from gofra.parser.exceptions import (
    ParserEntryPointFunctionModifiersError,
    ParserEntryPointFunctionTypeContractInError,
    ParserEntryPointFunctionTypeContractOutError,
    ParserNoEntryFunctionError,
)
from gofra.parser.functions.function import Function

from ._context import ParserContext


def validate_and_pop_entry_point(context: ParserContext) -> Function:
    """Validate program entry, check its existance and type contracts."""
    if GOFRA_ENTRY_POINT not in context.functions:
        raise ParserNoEntryFunctionError

    entry_point = context.functions.pop(GOFRA_ENTRY_POINT)
    if entry_point.external_definition_link_to or entry_point.emit_inline_body:
        raise ParserEntryPointFunctionModifiersError

    if entry_point.type_contract_out:
        raise ParserEntryPointFunctionTypeContractOutError(
            type_contract_out=entry_point.type_contract_out,
        )

    if entry_point.type_contract_out:
        raise ParserEntryPointFunctionTypeContractInError(
            type_contract_in=entry_point.type_contract_in,
        )
    return entry_point
