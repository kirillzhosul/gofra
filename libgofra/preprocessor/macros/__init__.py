"""Preprocessor macros parser/resolver."""

from .macro import Macro
from .preprocessor import (
    consume_macro_definition_from_token,
    try_resolve_and_expand_macro_reference_from_token,
)
from .registry import MacrosRegistry, registry_from_raw_definitions

__all__ = (
    "Macro",
    "MacrosRegistry",
    "consume_macro_definition_from_token",
    "registry_from_raw_definitions",
    "try_resolve_and_expand_macro_reference_from_token",
)
