from collections import deque
from copy import copy

from libgofra.hir.module import Module
from libgofra.optimizer.helpers.call_graph import CallGraph

DCE_TRACE_KILLS = False


def optimize_dead_code_elimination(
    module: Module,
    max_iterations: int,
    *,
    allow_aggressive_dce_from_entry_point: bool,
) -> None:
    """Perform DCE (dead-code-elimination) optimization onto program.

    Removes unused function from final program.
    TODO(@kirillzhosul): Does not optimize dead code.
    """
    if allow_aggressive_dce_from_entry_point:
        _dfs_dce_aggressive_on_main(module)
        return
    _bfs_dce_primitive(module, max_iterations)


def _bfs_dce_primitive(
    module: Module,
    max_iterations: int,
) -> None:
    """BFS DCE on module, traverse call graph for unused functions that is removable."""
    for _ in range(max_iterations):
        cg = CallGraph(module)

        for function in (f for f in cg.get_root_functions() if not f.is_public):
            assert function.module_path == module.path, (
                "Must be resolved and fixed later, please disable DCE on module system"
            )
            if DCE_TRACE_KILLS:
                print(f"DCE kill: {function.name}")
            module.functions.pop(function.name)


def _dfs_dce_aggressive_on_main(
    module: Module,
) -> None:
    """Perform DCE on module with DFS aggressively from main executable entry point, assuming it is executable.

    When we can assume that target is executable, we can DCE on call graph with DFS from main, and not flatten call graph
    This makes DCE more aggressive (goal -> remove EVERYTHING that is not called from main and underlying functions)
    Possibly this is an goal of LTO
    """
    assert module.entry_point_ref
    cg = CallGraph(module)

    main = cg.get_node(module.entry_point_ref)
    survivors = {main.function}
    pending = deque([main])

    while pending:
        current = pending.popleft()
        for callee in current.callees:
            if callee in survivors:
                continue
            pending.append(cg.get_node(callee))
            survivors.add(callee)

    ref = copy(module.functions)
    for f in ref.values():
        if f not in survivors:
            assert f.module_path == module.path

            if DCE_TRACE_KILLS:
                print(f"DCE kill: {f.name}")
            module.functions.pop(f.name)
