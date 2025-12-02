from gofra.hir.function import Function
from gofra.parser.exceptions import ParserEntryPointFunctionModifiersError
from gofra.typecheck.errors.entry_point_parameters_mismatch import (
    EntryPointParametersMismatchTypecheckError,
)
from gofra.typecheck.errors.entry_point_return_type_mismatch import (
    EntryPointReturnTypeMismatchTypecheckError,
)
from gofra.types.primitive.integers import I64Type


def validate_entry_point_signature(entry_point: Function) -> None:
    # TODO(@kirillzhosul): these parser errors comes from legacy entry point validation, must be reworked later - https://github.com/kirillzhosul/gofra/issues/28

    if entry_point.is_external or entry_point.is_inline:
        raise ParserEntryPointFunctionModifiersError

    retval_t = entry_point.return_type
    if entry_point.has_return_value() and not isinstance(retval_t, I64Type):
        raise EntryPointReturnTypeMismatchTypecheckError(return_type=retval_t)

    if entry_point.parameters:
        raise EntryPointParametersMismatchTypecheckError(
            parameters=entry_point.parameters,
        )
