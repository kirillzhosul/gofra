from collections.abc import Callable, MutableSequence
from functools import partial

from gofra.context import ProgramContext
from gofra.optimizer.config import OptimizerConfig

from .strategies import optimize_dead_code_elimination, optimize_function_inlining

type OPTIMIZER_PASS_T = Callable[[ProgramContext], None]
type OPTIMIZER_PIPELINE_T = MutableSequence[tuple[OPTIMIZER_PASS_T, str]]


def create_optimizer_pipeline(
    config: OptimizerConfig,
) -> OPTIMIZER_PIPELINE_T:
    """Build an optimizer `pipeline` from given config.

    You must apply each optimization pass for program context, they will mutate it.
    Each pass from pipeline contains
    """
    assert not config.do_algebraic_simplification, "TODO: do_algebraic_simplification!"
    assert not config.do_constant_folding, "TODO: do_constant_folding!"
    assert not config.do_strength_reduction, "TODO: do_strength_reduction!"

    pipeline: OPTIMIZER_PIPELINE_T = []

    if config.do_function_inlining:
        name = "Function inlining"
        pipe = _pipelined_function_inlining(
            max_operators=config.function_inlining_max_operators,
            max_iterations=config.function_inlining_max_iterations,
        )
        pipeline.append((pipe, name))

    if config.do_dead_code_elimination:
        name = "DCE (dead-code-elimination)"
        pipe = _pipelined_dead_code_elimination(
            max_iterations=config.dead_code_elimination_max_iterations,
        )
        pipeline.append((pipe, name))

    return pipeline


def _pipelined_dead_code_elimination(max_iterations: int) -> OPTIMIZER_PASS_T:
    return partial(optimize_dead_code_elimination, max_iterations=max_iterations)


def _pipelined_function_inlining(
    max_operators: int,
    max_iterations: int,
) -> OPTIMIZER_PASS_T:
    return partial(
        optimize_function_inlining,
        max_operators=max_operators,
        max_iterations=max_iterations,
    )
