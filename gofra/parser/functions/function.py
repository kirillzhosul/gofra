"""Function object as DTO and operations between stages."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from gofra.lexer.tokens import TokenLocation
    from gofra.parser.operators import Operator
    from gofra.typecheck.types import GofraType


# Both input and output type contracts are the same
type FunctionTypeContract = Sequence[GofraType]


class Function:
    """Language level function definition.

    Function is a sequence of operators (source body) that can be called by name

    For base functions it will define an executable region of code (real function) at code generation step
    `Extern` functions has no body and just an link for an external function
    `Inline` functions will be expanded within call (macros expansion) and will not be called like normal function

    Functions in Gofra are not first class functions
    They are not passed as arguments and are not returned from other functions
    They are just a sequence of operators (executable region of source body)
    """

    # Location of the function definition
    # Should not be used in any way for code generation or type checking
    # This is only for debugging purposes
    location: TokenLocation

    # Function will be called by that name
    # For extern functions, on different backends conventions is quite different
    # So on MacOS it will be prefixed with `_` and on Linux it will not
    name: str

    # Actual executable region that this function contains
    # If this is extern function will always be empty
    # If this is inline function will expand like there were no function
    source: Sequence[Operator]

    # Type contract `in -> out`
    # Specifies which types this function accepts and which - returns
    # Code generator will generate desired wrapper around that contract system
    # Type checker also validate usage of function so it does not be used with wrong contract
    type_contract_in: FunctionTypeContract
    type_contract_out: FunctionTypeContract

    # If true `function call` rather than proceeding into `jumping` (`calling`) into that function
    # just inject (emit) body of the function inside call target location (expand body of the function from call)
    # affects code generator so it wont generate native function block and will not use jumps
    # TODO(@kirillzhosul): Current implementation pollutes original definition source (expand whole operator/token sequence)
    emit_inline_body: bool

    # If given, function must have empty body as it is located somewhere else and only available after assembler step
    # Contains name of an external label (function)
    # Extern functions mostly are `C` functions (system/user defined) and call to them does jumps inside linked source binaries (dynamic libraries)
    # Code generator takes care of that calls and specifies extern function requests if needed (aggregates them for that)
    external_definition_link_to: str | None = None

    is_global_linker_symbol: bool = False

    def __init__(  # noqa: PLR0913
        self,
        *,
        location: TokenLocation,
        name: str,
        source: Sequence[Operator],
        type_contract_in: FunctionTypeContract,
        type_contract_out: FunctionTypeContract,
        emit_inline_body: bool,
        external_definition_link_to: str | None,
        is_global_linker_symbol: bool,
    ) -> None:
        self.location = location
        self.name = name
        self.source = source
        self.type_contract_in = type_contract_in
        self.type_contract_out = type_contract_out
        self.emit_inline_body = emit_inline_body
        self.external_definition_link_to = external_definition_link_to
        self.is_global_linker_symbol = is_global_linker_symbol
        self._validate()

    def _validate(self) -> None:
        """Validate internally that function is correct.

        Actual error handling should be before that and function object should not be created.
        """
        if self.external_definition_link_to:
            if self.emit_inline_body:
                msg = "Functions cannot be both marked as `inline` and `external`"
                raise ValueError(msg)
            if self.source:
                msg = "Functions that marked as `external` cannot have an body!"
                raise ValueError(msg)
            if self.is_global_linker_symbol:
                msg = "Functions that marked as `global` cannot have be external!"
                raise ValueError(msg)

        if not self.external_definition_link_to and not self.source:
            msg = "Functions that not marked as `external` must have an body!"
            raise ValueError(msg)

    def has_executable_body(self) -> bool:
        return not self.emit_inline_body and not self.external_definition_link_to

    def abi_ffi_push_retval_onto_stack(self) -> bool:
        return bool(self.external_definition_link_to) and bool(self.type_contract_out)
