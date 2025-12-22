from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator, MutableMapping
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

    # TODO(@kirillzhosul): This must be refactored into graph not within module itself.
    dependencies: MutableMapping[str, Module]

    def visit_dependencies(
        self,
        *,
        include_self: bool,
    ) -> Generator[Module]:
        if include_self:
            yield self

        visited: list[Module] = []
        pending: list[Module] = list(self.dependencies.values())
        while pending:
            current = pending.pop()
            if current in visited:
                continue
            visited.append(current)
            yield current
            if current.dependencies:
                pending.extend(current.dependencies.values())

    def resolve_function_dependency(
        self,
        module: str | None,
        func: str,
    ) -> Function | None:
        """Find given function named inside current module and its dependencies.

        If function is not found returns None.
        When module is None - search only in current module.

        Module specifies which module name (import as) holds that function symbol
        """
        if module is None:
            return self.functions.get(func)

        hir_module = self.dependencies.get(module)
        if not hir_module:
            return None  # Module is not an dependency of current module
        return hir_module.resolve_function_dependency(
            module=None,
            func=func,
        )

    def flatten_dependencies_paths(self, *, include_self: bool) -> set[Path]:
        flatten: set[Path] = {self.path} if include_self else set()
        for children in (
            m.flatten_dependencies_paths(include_self=True)
            for m in self.dependencies.values()
        ):
            flatten.update(children)
        return flatten

    @property
    def executable_functions(self) -> filter[Function]:
        return filter(
            lambda f: not f.is_external,
            self.functions.values(),
        )
