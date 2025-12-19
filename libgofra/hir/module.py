from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import MutableMapping
    from pathlib import Path

    from libgofra.hir.function import Function
    from libgofra.hir.variable import Variable
    from libgofra.types._base import Type
    from libgofra.types.composite.structure import StructureType


@dataclass(frozen=True, slots=True)
class Module:
    """HIR compilation (parsing) unit or module for an preprocessed (is applicable) file.

    Contains definitions from that preprocessed unit/module file.
    (Using unit terminology as an analogy for C/C++ translation/compilation units)
    """

    # Location of an file which this module initial parsed from (excluding preprocessor stages)
    path: Path

    # Any function that this module defines (implements, externs, exports)
    functions: MutableMapping[str, Function]

    # Global functions that this module defines (excluding static variables inside function)
    # notice that static variables inside function is held inside functions
    variables: MutableMapping[str, Variable[Type]]

    # Structures that this module defines (can be unused)
    structures: MutableMapping[str, StructureType]

    @property
    def executable_functions(self) -> filter[Function]:
        return filter(
            lambda f: not f.is_external,
            self.functions.values(),
        )
