"""Optimization strategies applied to the program to optimize it."""

from .dead_code_elimination import optimize_dead_code_elimination
from .function_inlining import optimize_function_inlining

__all__ = ["optimize_dead_code_elimination", "optimize_function_inlining"]
