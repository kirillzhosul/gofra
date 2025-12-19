from collections import deque
from collections.abc import Mapping
from typing import Self

from libgofra.lexer.lexer import tokenize_from_raw
from libgofra.lexer.tokens import TokenLocation
from libgofra.preprocessor.macros.defaults import (
    construct_propagated_toolchain_definitions,
)
from libgofra.targets.target import Target

from .macro import Macro


class MacrosRegistry(dict[str, Macro]):
    """Top-level preprocessor mapping of macros."""

    def new(self, location: TokenLocation, name: str) -> Macro:
        """Create empty macro that located at given location to fill it with preprocessed tokens."""
        macro = Macro(location=location, name=name)
        self.__setitem__(name, macro)
        return macro

    def inject_propagated_defaults(self, target: Target) -> Self:
        definitions = construct_propagated_toolchain_definitions(
            target=target,
        )
        injected_registry = registry_from_raw_definitions(
            location=TokenLocation.toolchain(),
            definitions=definitions,
        )

        self.update(injected_registry)
        return self

    def copy(self) -> "MacrosRegistry":
        return MacrosRegistry(super().copy())


def registry_from_raw_definitions(
    location: TokenLocation,
    definitions: Mapping[str, str],
) -> MacrosRegistry:
    """Construct new macros registry from given 'raw' definitions (text, that need lexing).

    Definition is implied to be single-line.
    Location must not be from an `file` source as in that scenario you must use different approaches like preprocessing another file.
    """
    if location.source == "file":
        msg = (
            f"`{registry_from_raw_definitions.__name__}` implies raw definitions, but tried to pass parent location with `file` source, which is consider as an fatal error.\n"
            "Consider using other ways to propagate macros (e.g via preprocessing that file and merging their registry, or pass location with proper source.)"
        )
        raise ValueError(msg)

    registry = MacrosRegistry()
    for name, definition in definitions.items():
        # Tokenize each definition with propagated source
        # (as this functions does not imply that definition source is from an file and probably this wont be that scenario)
        tokenizer = tokenize_from_raw(source=location.source, lines=[definition])
        tokens = deque(tokenizer)

        macro = Macro(location=location, name=name, tokens=tokens)
        registry[name] = macro
    return registry
