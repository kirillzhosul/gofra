"""Function object as DTO and operations between stages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from gofra.hir.operator import OperatorType
from gofra.types.primitive.void import VoidType

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from gofra.hir.operator import Operator
    from gofra.hir.variable import Variable
    from gofra.lexer.tokens import TokenLocation
    from gofra.types import Type


@dataclass(frozen=False, slots=True, init=False)
class Function:
    """HIR Language level function container.

    Function is a sequence of operators (source body) that can be called by name

    For base functions it will define an executable region of code (real function) at code generation step
    `Extern` functions has no body and just an link for an external function
    `Inline` functions will be expanded within call (macros expansion) and will not be called like normal function
    """

    # Function will be called by that name in Gofra source
    name: str

    # Location of the function definition
    # Should not be used in any way for code generation or type checking
    # This is only for debugging purposes
    defined_at: TokenLocation

    # Local variables defined inside that function
    # only that function can reference them and location of that variable is different as codegen may solve that
    variables: Mapping[str, Variable]

    # Actual executable block that this function contains
    # If this is extern function will always be empty
    # If this is inline function will expand without actual function call
    operators: Sequence[Operator]

    # Parameter types of the function that it accepts
    # e.g type contract-in
    parameters: Sequence[Type]

    # If true, calling that function instead of actual calling into that function
    # just expands body of the function inside call location
    is_inline: bool

    # If true, function must have empty body and it is located somewhere else and only available after linkage
    # Extern functions mostly are `C` functions (system/user defined) and call to them does jumps inside linked source binaries (dynamic libraries)
    # Code generator takes care of that calls and specifies extern function requests if needed (aggregates them for that)
    is_external: bool

    # If true, marks that function as *global* for linkage with another objects
    # Global functions can be linked with other binary files after compilation (e.g for libraries development)
    is_global: bool

    # If true, means function has no calls to other functions
    # Allows some HIR (but mostly treated as metadata for LIR optimizations)
    is_leaf: bool

    # Value type for retval (e.g type of the value which function returns)
    # Void type means function has no return value and codegen must omit storing retval
    return_type: Type

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

    def has_return_value(self) -> bool:
        """Check is given function returns an void type (e.g no return type)."""
        # This meant to be something like generic function class / type guards but Python is shi...
        return not isinstance(self.return_type, VoidType)

    @property
    def has_executable_operators(self) -> bool:
        """If true, function has any operators to execute (compile)."""
        return bool(self.operators)

    @property
    def has_local_variables(self) -> bool:
        """Function has one or more local variables."""
        return bool(self.variables)

    @property
    def arguments_count(self) -> int:
        """Arguments (parameters) amount which this function expects."""
        return len(self.parameters)

    @classmethod
    def create_external(
        cls,
        *,
        name: str,
        defined_at: TokenLocation,
        parameters: Sequence[Type],
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
            is_global=False,
            is_external=True,
        )

    @classmethod
    def create_internal_inline(
        cls,
        *,
        name: str,
        defined_at: TokenLocation,
        parameters: Sequence[Type],
        operators: Sequence[Operator],
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
            is_global=False,
            is_external=False,
        )

    @classmethod
    def create_internal(  # noqa: PLR0913
        cls,
        *,
        name: str,
        defined_at: TokenLocation,
        parameters: Sequence[Type],
        variables: Mapping[str, Variable],
        operators: Sequence[Operator],
        return_type: Type,
        is_global: bool,
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
            is_global=is_global,
            is_inline=False,
            is_external=False,
        )

    @classmethod
    def _create(  # noqa: PLR0913
        cls,
        *,
        name: str,
        defined_at: TokenLocation,
        parameters: Sequence[Type],
        variables: Mapping[str, Variable] | None,
        operators: Sequence[Operator] | None,
        return_type: Type,
        is_global: bool,
        is_leaf: bool,
        is_inline: bool,
        is_external: bool,
    ) -> Self:
        """Alternative for __init__ that is wrapped by factory methods (`create_*`)."""
        function = cls()
        function.name = name
        function.defined_at = defined_at
        function.defined_at = defined_at
        function.parameters = parameters
        function.return_type = return_type
        function.variables = variables or {}
        function.operators = operators or []
        function.is_global = is_global
        function.is_leaf = is_leaf
        function.is_inline = is_inline
        function.is_external = is_external

        # Assertion-style validation
        # Must be validated in higher layer

        if variables and is_inline:
            msg = "Inline functions cannot have local variables. Bug in HIR"
            raise ValueError(msg)

        if variables and is_external:
            msg = "External function cannot have local variables. Bug in HIR"
            raise ValueError(msg)

        return function
