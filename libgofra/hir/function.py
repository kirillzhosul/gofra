"""Function object as DTO and operations between stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Self

from libgofra.hir.operator import OperatorType
from libgofra.types.primitive.void import VoidType

if TYPE_CHECKING:
    from collections.abc import Mapping, MutableSequence, Sequence

    from libgofra.hir.module import Module
    from libgofra.hir.operator import Operator
    from libgofra.hir.variable import Variable
    from libgofra.lexer.tokens import TokenLocation
    from libgofra.types import Type


type PARAMS_T = Sequence[Type]


class Visibility(Enum):
    """How this symbol (e.g function, variable) is visible to other modules.

    E.g with public visibility - anyone can access that symbol and it will be visible
    with private - only usage in owner module itself is allowed (must not be linked with other object files)
    """

    PUBLIC = auto()  # Allowed from everywhere
    PRIVATE = auto()  # Only inside current module


class FunctionInlineAttribute(Enum):
    DEFAULT = auto()
    NEVER = auto()
    ALWAYS = auto()

    def __bool__(self) -> bool:
        return self.value == FunctionInlineAttribute.ALWAYS.value


@dataclass(init=True, repr=True, eq=False, frozen=False, kw_only=True)
class FunctionAttributes:
    # If true, calling that function instead of actual calling into that function
    # just expands body of the function inside call location
    inline: FunctionInlineAttribute = field(
        repr=True,
        default=FunctionInlineAttribute.DEFAULT,
    )

    # If true, function must have empty body and it is located somewhere else and only available after linkage
    # Extern functions mostly are `C` functions (system/user defined) and call to them does jumps inside linked source binaries (dynamic libraries)
    # Code generator takes care of that calls and specifies extern function requests if needed (aggregates them for that)
    external: bool = field(repr=True, default=False)

    # If true, functions does not generate appropriate prolog and epilogue in codegen
    # and must consist only from inline assembly instructions
    naked: bool = field(repr=False, default=False)

    # If true, means function cannot *return*
    # E.g is explicitly `exit` function as it must never returns
    # Allows to treat blocks after as unreachable and perform optional DCE onto it
    no_return: bool = field(repr=False, default=False)

    # Sharing of this functions within exports/modules
    # By default all are private
    visibility: Visibility = field(default=Visibility.PRIVATE)

    # If true, function has no calls to other functions
    # compiler may perform some optimizations for these
    leaf: bool = field(repr=False, default=False)

    # If true, has calls to itself, affects optimizations and some errors
    recursive: bool = field(repr=False, default=False)


@dataclass(frozen=False, slots=True, init=False)
class Function:
    """HIR Language level function container.

    Function is a sequence of operators (source body) that can be called by name

    For base functions it will define an executable region of code (real function) at code generation step
    `Extern` functions has no body and just an link for an external function
    `Inline` functions will be expanded within call (macros expansion) and will not be called like normal function
    """

    # fmt: off
    name:        str                           = field(repr=True)
    defined_at:   TokenLocation                 = field(repr=True)
    parameters:  PARAMS_T                      = field(repr=True)
    return_type: Type                          = field(repr=True) # Void -> no return

    module:      Module                        = field(repr=False)
    variables:   Mapping[str, Variable[Type]]  = field(repr=False) # Local ones, excluding parameters
    attrs:       FunctionAttributes            = field(repr=True)

    operators:   MutableSequence[Operator]     = field(repr=False)

    outer_function: Function | None            = field(repr=False)
    # fmt: on

    def has_return_value(self) -> bool:
        """Check is given function returns an void type (e.g no return type)."""
        return not isinstance(self.return_type, VoidType)

    @property
    def is_public(self) -> bool:
        return self.attrs.visibility == Visibility.PUBLIC

    @property
    def has_relative_jumps(self) -> bool:
        """If true, function has relative jumps (e.g loops, ifs, etc)."""
        return any(
            operator.jumps_to_operator_idx is not None for operator in self.operators
        )

    @classmethod
    def create_external(
        cls,
        *,
        name: str,
        defined_at: TokenLocation,
        parameters: PARAMS_T,
        return_type: Type,
    ) -> Self:
        """Create function that is external, with propagated flags set."""
        return cls._create(
            name=name,
            defined_at=defined_at,
            parameters=parameters,
            return_type=return_type,
            variables=None,
            operators=None,
            is_inline=False,
            is_external=True,
        )

    @classmethod
    def create_internal_inline(
        cls,
        *,
        name: str,
        defined_at: TokenLocation,
        parameters: PARAMS_T,
        operators: MutableSequence[Operator],
        return_type: Type,
    ) -> Function:
        """Create function that is internal and inline, with propagated flags set."""
        return cls._create(
            name=name,
            defined_at=defined_at,
            parameters=parameters,
            return_type=return_type,
            operators=operators,
            variables=None,
            is_inline=True,
            is_external=False,
        )

    @classmethod
    def create_internal(  # noqa: PLR0913
        cls,
        *,
        name: str,
        defined_at: TokenLocation,
        parameters: PARAMS_T,
        variables: Mapping[str, Variable[Type]],
        operators: MutableSequence[Operator],
        return_type: Type,
    ) -> Function:
        """Create function that is internal and not inline, with propagated flags set."""
        return cls._create(
            name=name,
            defined_at=defined_at,
            parameters=parameters,
            return_type=return_type,
            variables=variables,
            operators=operators,
            is_inline=False,
            is_external=False,
        )

    @classmethod
    def _create(  # noqa: PLR0913
        cls,
        *,
        name: str,
        defined_at: TokenLocation,
        parameters: PARAMS_T,
        variables: Mapping[str, Variable[Type]] | None,
        operators: MutableSequence[Operator] | None,
        return_type: Type,
        is_inline: bool,
        is_external: bool,
    ) -> Self:
        """Alternative for __init__ that is wrapped by factory methods (`create_*`)."""
        function = cls()
        function.name = name
        function.defined_at = defined_at
        function.parameters = parameters
        function.return_type = return_type
        function.variables = variables or {}
        function.operators = operators or []
        function.outer_function = None

        inline_attr = (
            FunctionInlineAttribute.ALWAYS
            if is_inline
            else FunctionInlineAttribute.DEFAULT
        )
        recursive_attr = (
            any(
                operator.type == OperatorType.FUNCTION_CALL and operator.operand == name
                for operator in operators
            )
            if operators
            else False
        )
        function.attrs = FunctionAttributes(
            external=is_external,
            inline=inline_attr,
            visibility=Visibility.PRIVATE,
            recursive=recursive_attr,
        )

        # Assertion-style validation
        # Must be validated in higher layer

        if variables and is_inline:
            msg = "Inline functions cannot have local variables. Bug in HIR"
            raise ValueError(msg)

        if variables and is_external:
            msg = "External function cannot have local variables. Bug in HIR"
            raise ValueError(msg)

        return function

    def __hash__(self) -> int:
        return hash(str(self.module.path) + self.name)
