import operator as python_operator
from collections import deque
from collections.abc import Callable, MutableSequence, Sequence

from gofra.context import ProgramContext
from gofra.lexer import Token, TokenType
from gofra.parser import Operator, OperatorType
from gofra.parser.intrinsics import Intrinsic
from gofra.typecheck.types import GofraType

type BinaryIntFoldPredicate = Callable[[int, int], int]
BINARY_INT_INTRINSIC_FOLD_PREDICATES: dict[Intrinsic, BinaryIntFoldPredicate] = {
    Intrinsic.PLUS: python_operator.add,
    Intrinsic.MINUS: python_operator.sub,
    Intrinsic.MULTIPLY: python_operator.mul,
    Intrinsic.DIVIDE: python_operator.truediv,
    Intrinsic.MODULUS: python_operator.mod,
    Intrinsic.EQUAL: python_operator.eq,
    Intrinsic.NOT_EQUAL: python_operator.ne,
    Intrinsic.LESS_THAN: python_operator.lt,
    Intrinsic.GREATER_THAN: python_operator.gt,
    Intrinsic.LESS_EQUAL_THAN: python_operator.le,
    Intrinsic.GREATER_EQUAL_THAN: python_operator.ge,
}


def optimize_constant_folding(program: ProgramContext) -> None:
    """Optimize given operators so they dont left unfolded into useless operators.

    For example: 2 2 + folds into single push 4
    or operations that results into dropping from stack being eliminated
    """
    # TODO(@kirillzhosul): This should be refactored due to refactoring core.
    return
    for function in (*program.functions.values(), program.entry_point):
        function.source = _fold_operators(function.source)


def _fold_operators(unoptimized: Sequence[Operator]) -> Sequence[Operator]:
    non_optimizable_offset = 2
    if len(unoptimized) < non_optimizable_offset:
        return unoptimized

    optimized = deque(unoptimized[:non_optimizable_offset])
    jump_idx_left_shift = 0

    open_ctx_stack: list[Operator] = [
        operator
        for operator in optimized
        if operator.type in (OperatorType.DO, OperatorType.IF)
    ]

    def shift_unoptimized_operator() -> None:
        op = optimized[-1]
        if op.jumps_to_operator_idx is not None:
            op.jumps_to_operator_idx = max(
                op.jumps_to_operator_idx - int(jump_idx_left_shift),
                0,
            )

    def shift_open_ctx_operator(shifted_left_by: int) -> None:
        assert len(open_ctx_stack) > 0

        ctx_operator = open_ctx_stack.pop()

        assert ctx_operator.jumps_to_operator_idx is not None
        ctx_operator.jumps_to_operator_idx -= shifted_left_by

    for idx, operator in enumerate(unoptimized[2:], start=2):
        if operator.type in (OperatorType.DO, OperatorType.IF):
            open_ctx_stack.append(operator)
            optimized.append(operator)
            continue

        if operator.type == OperatorType.END:
            optimized.append(operator)
            shift_unoptimized_operator()
            shift_open_ctx_operator(shifted_left_by=jump_idx_left_shift)
            continue

        if operator.type != OperatorType.INTRINSIC:
            optimized.append(operator)
            shift_unoptimized_operator()
            continue

        assert isinstance(operator.operand, Intrinsic)

        if operator.operand == Intrinsic.DROP:
            prev_operator = optimized[-1]
            if prev_operator.type == OperatorType.PUSH_INTEGER:
                optimized.pop()
                jump_idx_left_shift += 2
                continue
            if (
                prev_operator.is_syscall()
                and prev_operator.syscall_optimization_omit_result is False
            ):
                prev_operator.syscall_optimization_omit_result = True
                prev_operator.has_optimizations = True
                jump_idx_left_shift += 1
                continue

        if (
            operator.is_syscall()
            and operator.syscall_optimization_injected_args is None
        ):
            args_count = operator.get_syscall_arguments_count()
            for arg_n in range(args_count):
                arg_operator = optimized.pop()
                if arg_operator.type != OperatorType.PUSH_INTEGER:
                    optimized.append(arg_operator)
                    break

                if operator.syscall_optimization_injected_args is None:
                    operator.has_optimizations = True
                    operator.syscall_optimization_injected_args = [
                        None for _ in range(args_count)
                    ]

                assert isinstance(arg_operator.operand, int)
                operator.syscall_optimization_injected_args[arg_n] = (
                    arg_operator.operand
                )
                jump_idx_left_shift += 1
            if operator.syscall_optimization_injected_args:
                operator.syscall_optimization_injected_args = list(
                    reversed(operator.syscall_optimization_injected_args),
                )
            optimized.append(operator)
            continue

        fold_predicate = BINARY_INT_INTRINSIC_FOLD_PREDICATES.get(operator.operand)
        if fold_predicate is None:
            optimized.append(operator)
            shift_unoptimized_operator()
            continue

        was_folded = _fold_binary_integer_math_operator(
            idx,
            optimized,
            unoptimized,
            fold_predicate=fold_predicate,
        )
        if not was_folded:
            optimized.append(operator)
            shift_unoptimized_operator()
            continue

        jump_idx_left_shift += 2
        shift_unoptimized_operator()

    if jump_idx_left_shift > 0:
        return _fold_operators(unoptimized=list(optimized))

    return optimized


def _fold_binary_integer_math_operator(
    idx: int,
    optimized: MutableSequence[Operator],
    unoptimized: Sequence[Operator],
    *,
    fold_predicate: BinaryIntFoldPredicate,
) -> bool:
    operators = [unoptimized[idx - 1], unoptimized[idx - 2]]

    if not (operators[0].type == operators[1].type == OperatorType.PUSH_INTEGER):
        return False

    operands = [operators[0].operand, operators[1].operand]
    assert isinstance(operands[0], int)
    assert isinstance(operands[1], int)

    infer_type = GofraType.INTEGER
    folded_value = fold_predicate(operands[0], operands[1])
    if isinstance(folded_value, bool):
        infer_type = GofraType.BOOLEAN

    folded_value = int(folded_value)

    optimized.pop()
    optimized.pop()

    operator = Operator(
        type=OperatorType.PUSH_INTEGER,
        token=Token(
            type=TokenType.INTEGER,
            text="__optimized__",
            value=folded_value,
            location=unoptimized[idx].token.location,
        ),
        operand=folded_value,
        has_optimizations=True,
        infer_type_after_optimization=infer_type,
    )

    optimized.append(operator)
    return True
