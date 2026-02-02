from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Literal, assert_never

type OPTIMIZER_LEVEL = Literal[0, 1]


@dataclass
class OptimizerConfig:
    """Configuration for optimizer passes."""

    level: OPTIMIZER_LEVEL

    # Feature flags
    do_function_inlining: bool
    do_dead_code_elimination: bool
    do_constant_folding: bool
    do_algebraic_simplification: bool
    do_strength_reduction: bool

    # Codegen-specific
    codegen_omit_unused_frame_pointer: bool
    codegen_peephole_isa_optimizer: bool

    # Specific options
    dead_code_aggressive_from_entry_point: bool = False

    # Fine tuning optimizations
    function_inlining_max_operators: int = 10
    function_inlining_max_iterations: int = 128
    dead_code_elimination_max_iterations: int = 128


def build_default_optimizer_config_from_level(
    level: OPTIMIZER_LEVEL,
) -> OptimizerConfig:
    """Construct optimizer config with default settings inferred from level."""
    if level == 0:
        return OptimizerConfig(
            level=level,
            do_function_inlining=False,
            do_dead_code_elimination=False,
            do_constant_folding=False,
            do_algebraic_simplification=False,
            do_strength_reduction=False,
            codegen_omit_unused_frame_pointer=False,
            codegen_peephole_isa_optimizer=False,
        )
    if level == 1:
        return OptimizerConfig(
            level=level,
            do_dead_code_elimination=True,
            do_function_inlining=True,
            codegen_omit_unused_frame_pointer=True,
            codegen_peephole_isa_optimizer=True,
            # TODO(@kirillzhosul): Those optimizations are pending to be implemented.
            do_constant_folding=False,
            do_algebraic_simplification=False,
            do_strength_reduction=False,
        )

    assert_never(level)


def merge_into_optimizer_config(
    config: OptimizerConfig,
    from_object: object,
    *,
    prefix: str = "",
) -> OptimizerConfig:
    for field in dataclasses.fields(OptimizerConfig):
        from_name = prefix + "_" + field.name
        if hasattr(from_object, from_name):
            arg_value = getattr(from_object, from_name)
            if arg_value is not None:
                setattr(config, field.name, arg_value)
    return config
