"""Entry point validator.

Probably should not be here (in parser)
"""

from gofra.consts import GOFRA_ENTRY_POINT
from gofra.hir.function import Function
from gofra.parser.exceptions import (
    ParserEntryPointFunctionModifiersError,
    ParserEntryPointFunctionTypeContractInError,
    ParserEntryPointFunctionTypeContractOutError,
    ParserNoEntryFunctionError,
)
from gofra.types.primitive.void import VoidType

from ._context import ParserContext


def validate_and_pop_entry_point(context: ParserContext) -> Function:
    """Validate program entry, check its existence and type contracts."""
    if GOFRA_ENTRY_POINT not in context.functions:
        raise ParserNoEntryFunctionError

    entry_point = context.functions.pop(GOFRA_ENTRY_POINT)
    if entry_point.is_external or entry_point.is_inline:
        raise ParserEntryPointFunctionModifiersError

    if not isinstance(entry_point.return_type, VoidType):
        raise ParserEntryPointFunctionTypeContractOutError(
            type_contract_out=entry_point.return_type,
        )

    if entry_point.parameters:
        raise ParserEntryPointFunctionTypeContractInError(
            parameters=entry_point.parameters,
        )
    return entry_point
