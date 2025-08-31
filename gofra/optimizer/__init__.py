"""Optimizer package that used to apply different optimizations strategies for program."""

from .config import build_default_optimizer_config_from_level
from .pipeline import create_optimizer_pipeline

__all__ = (
    "build_default_optimizer_config_from_level",
    "create_optimizer_pipeline",
)
