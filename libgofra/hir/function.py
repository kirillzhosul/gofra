"""Function object as DTO and operations between stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Self

from libgofra.hir.operator import OperatorType
from libgofra.types.primitive.void import VoidType

if TYPE_CHECKING:
    from collections.abc import Mapping, MutableSequence, Sequence
    from pathlib import Path

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


@dataclass(frozen=False, slots=True, init=False)
class Function:
    """HIR Language level function container.

    Function is a sequence of operators (source body) that can be called by name

    For base functions it will define an executable region of code (real function) at code generation step
    `Extern` functions has no body and just an link for an external function
    `Inline` functions will be expanded within call (macros expansion) and will not be called like normal function
    """

    # Path to an module which defined that function
    module_path: Path = field(repr=False)

    # Function will is callable by this name in Gofra source
    name: str

    # Location of the function definition
    # Should not be used in any way for code generation or type checking
    # This is only for debugging purposes
    defined_at: TokenLocation

    # Local variables defined inside that function
    # only that function can reference them and location of that variable is different as codegen may solve that
    variables: Mapping[str, Variable[Type]] = field(repr=False)

    # Actual executable block that this function contains
    # If this is extern function will always be empty
    # If this is inline function will expand without actual function call
    operators: MutableSequence[Operator] = field(repr=False)

    # Parameter types of the function that it accepts
    # e.g type contract-in
    parameters: PARAMS_T

    # Sharing of this functions within exports/modules
    # By default all are private
    visibility: Visibility = field(default=Visibility.PRIVATE)

    # If true, calling that function instead of actual calling into that function
    # just expands body of the function inside call location
    is_inline: bool = field(repr=False)

    # If true, means function cannot *return*
    # E.g is explicitly `exit` function as it must never returns
    # Allows to treat blocks after as unreachable and perform optional DCE onto it
    is_no_return: bool = field(repr=False)

    # If true, function must have empty body and it is located somewhere else and only available after linkage
    # Extern functions mostly are `C` functions (system/user defined) and call to them does jumps inside linked source binaries (dynamic libraries)
    # Code generator takes care of that calls and specifies extern function requests if needed (aggregates them for that)
    is_external: bool

    # If true, function has no calls to other functions
    # compiler may perform some optimizations for these
    is_leaf: bool = field(repr=False)

    # Type of return value (type of data which this functions returns after call)
    # When there is void / never type - function does not have return type
    # compiler in this case may omit return value and perform general optimizations based on return value
    return_type: Type

    enclosed_functions: Sequence[Function] | None = field(repr=False)
    enclosed_in_parent: Function | None = field(repr=False)

    def has_return_value(self) -> bool:
        """Check is given function returns an void type (e.g no return type)."""
        # This meant to be something like generic function class / type guards but Python is shi...
        return not isinstance(self.return_type, VoidType)

    @property
    def is_public(self) -> bool:
        return self.visibility == Visibility.PUBLIC

    @property
    def is_recursive(self) -> bool:
        """If true, function has call to itself.

        Mark for some HIR optimizations as this function impossible to optimize with some strategies.
        """
        # TODO(@kirillzhosul): Optimize that for compile-time check
        return any(
            operator.type == OperatorType.FUNCTION_CALL
            and operator.operand == self.name
            for operator in self.operators
        )

    @property
    def has_executable_operators(self) -> bool:
        """If true, function has any operators to execute (compile)."""
        return bool(self.operators)

    @property
    def has_local_variables(self) -> bool:
        """Function has one or more local variables."""
        return bool(self.variables)

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
            is_leaf=False,
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
            is_leaf=False,
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
        is_leaf: bool,
    ) -> Function:
        """Create function that is internal and not inline, with propagated flags set."""
        return cls._create(
            name=name,
            defined_at=defined_at,
            parameters=parameters,
            return_type=return_type,
            variables=variables,
            operators=operators,
            is_leaf=is_leaf,
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
        is_leaf: bool,
        is_inline: bool,
        is_external: bool,
    ) -> Self:
        """Alternative for __init__ that is wrapped by factory methods (`create_*`)."""
        function = cls()
        function.visibility = Visibility.PRIVATE
        function.name = name
        function.defined_at = defined_at
        function.defined_at = defined_at
        function.parameters = parameters
        function.return_type = return_type
        function.variables = variables or {}
        function.operators = operators or []
        function.is_leaf = is_leaf
        function.is_inline = is_inline
        function.is_external = is_external
        function.is_no_return = False
        function.enclosed_functions = None
        function.enclosed_in_parent = None
        # Assertion-style validation
        # Must be validated in higher layer

        if variables and is_inline:
            msg = "Inline functions cannot have local variables. Bug in HIR"
            raise ValueError(msg)

        if variables and is_external:
            msg = "External function cannot have local variables. Bug in HIR"
            raise ValueError(msg)

        return function
