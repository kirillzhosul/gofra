from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from gofra.parser.operators import Operator

from .exceptions import (
    TypecheckInvalidFunctionArgumentTypeError,
    TypecheckInvalidOperatorArgumentTypeError,
    TypecheckNotEnoughFunctionArgumentsError,
    TypecheckNotEnoughOperatorArgumentsError,
)
from .types import GofraType as T

if TYPE_CHECKING:
    from collections.abc import MutableSequence

    from gofra.parser.functions.function import Function


@dataclass(frozen=False)
class TypecheckContext:
    """Context for type checking which only required for internal usages."""

    # Typechecker is an emulated type stack, e.g 1 2 would produce [INT, INT] ino type stack
    emulated_stack_types: MutableSequence[T]

    def push_types(self, *types: T) -> None:
        """Push given types onto emulated typeS stack."""
        self.emulated_stack_types.extend(types)

    def raise_for_enough_arguments(
        self,
        operator_or_function: Operator | Function,
        inside_function: Function,
        required_args: int,
        operator: Operator | None = None,
    ) -> None:
        """Expect that stack has N arguments."""
        stack_size = len(self.emulated_stack_types)
        if stack_size < required_args:
            if isinstance(operator_or_function, Operator):
                raise TypecheckNotEnoughOperatorArgumentsError(
                    operator=operator_or_function,
                    types_on_stack=self.emulated_stack_types,
                    required_args=required_args,
                )
            assert operator, "Expected call operator"
            raise TypecheckNotEnoughFunctionArgumentsError(
                function=operator_or_function,
                callee_function=inside_function,
                types_on_stack=self.emulated_stack_types,
                called_from_operator=operator,
            )

    def pop_type_from_stack(self) -> T:
        """Pop current type on the stack."""
        return self.emulated_stack_types.pop()

    def consume_n_arguments(self, args_to_consume: int) -> None:
        """Pop N arguments from stack of any type."""
        for _ in range(args_to_consume):
            self.pop_type_from_stack()

    def raise_for_arguments(
        self,
        operator_or_function: Operator | Function,
        inside_function: Function,
        *expected_types: T,
        operator: Operator | None = None,
    ) -> None:
        """Expect given arguments and count and their types should match.

        Types are reversed so call will look like original stack.
        """
        assert expected_types, "Expected at least one type to expect"
        assert isinstance(operator_or_function, Operator) or operator is not None, (
            "Expecting arguments from an function requires call operator"
        )
        self.raise_for_enough_arguments(
            operator_or_function,
            inside_function,
            len(expected_types),
            operator=operator,
        )
        _reference_type_stack = self.emulated_stack_types[::]
        for expected_type in expected_types[::-1]:
            argument_type = self.pop_type_from_stack()
            if expected_type not in (T.ANY, argument_type):
                if isinstance(operator_or_function, Operator):
                    raise TypecheckInvalidOperatorArgumentTypeError(
                        operator=operator_or_function,
                        actual_type=argument_type,
                        expected_type=expected_type,
                        type_stack=_reference_type_stack,
                        contract=expected_types,
                    )
                raise TypecheckInvalidFunctionArgumentTypeError(
                    function=operator_or_function,
                    actual_type=argument_type,
                    expected_type=expected_type,
                )
