from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from gofra.typecheck.errors import (
    MissingFunctionArgumentsTypecheckError,
    ParameterTypeMismatchTypecheckError,
)
from gofra.types.comparison import is_types_same

from .exceptions import (
    TypecheckInvalidOperatorArgumentTypeError,
    TypecheckNotEnoughOperatorArgumentsError,
)

if TYPE_CHECKING:
    from collections.abc import MutableSequence

    from gofra.hir.function import Function
    from gofra.hir.operator import Operator
    from gofra.types import Type


@dataclass(frozen=False)
class TypecheckScope:
    """Scope (context) for type checking which only required for internal usages."""

    # Typechecker is an emulated type stack, e.g 1 2 would produce [INT, INT] ino type stack
    types: MutableSequence[Type]

    def push_types(self, *types: Type) -> None:
        """Push given types onto emulated types stack."""
        self.types.extend(types)

    def raise_for_enough_arguments(
        self,
        operator: Operator,
        required_args: int,
    ) -> None:
        """Expect that stack has N arguments."""
        stack_size = len(self.types)
        if stack_size < required_args:
            raise TypecheckNotEnoughOperatorArgumentsError(
                operator=operator,
                types_on_stack=self.types,
                required_args=required_args,
            )

    def pop_type_from_stack(self) -> Type:
        """Pop current type on the stack."""
        return self.types.pop()

    def consume_n_arguments(self, args_to_consume: int) -> None:
        """Pop N arguments from stack of any type."""
        for _ in range(args_to_consume):
            self.pop_type_from_stack()

    def raise_for_function_arguments(
        self,
        callee: Function,
        caller: Function,
        at: Operator,
    ) -> None:
        """Expect given arguments and count and their types should match.

        Types are reversed so call will look like original stack.
        """
        stack_size = len(self.types)
        if stack_size < len(callee.parameters):
            raise MissingFunctionArgumentsTypecheckError(
                typestack=self.types,
                callee=callee,
                caller=caller,
                at=at.location,
            )

        for expected_type in callee.parameters[::-1]:
            argument_type = self.pop_type_from_stack()

            if is_types_same(
                argument_type,
                expected_type,
                strategy="strict-same-type",
            ):
                continue

            # TODO(@kirillzhosul): Called from `real_function` at `inlined_location` (bug)
            raise ParameterTypeMismatchTypecheckError(
                expected_type=expected_type,
                actual_type=argument_type,
                caller=caller,
                callee=callee,
                at=at.location,
            )

    def raise_for_operator_arguments(
        self,
        operator: Operator,
        *expected_types: tuple[type[Type], ...],
    ) -> None:
        """Expect given arguments and count and their types should match.

        Types are reversed so call will look like original stack.
        """
        assert expected_types, "Expected at least one type to expect"
        self.raise_for_enough_arguments(
            operator,
            len(expected_types),
        )

        # Store shallow copy as we mutate that but want to display proper error with stack before our manipulations
        _reference_type_stack = self.types[::]

        for expected_type in expected_types[::-1]:
            argument_type = self.pop_type_from_stack()

            if isinstance(argument_type, expected_type):
                continue

            raise TypecheckInvalidOperatorArgumentTypeError(
                operator=operator,
                actual_type=argument_type,
                expected_type=expected_type,
                type_stack=_reference_type_stack,
                contract=expected_types,
            )
