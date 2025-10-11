from gofra.hir.module import Module
from gofra.optimizer.helpers.function_usage import search_unused_functions


def optimize_dead_code_elimination(
    program: Module,
    max_iterations: int,
) -> None:
    """Perform DCE (dead-code-elimination) optimization onto program.

    Removes unused function from final program.
    TODO(@kirillzhosul): Does not optimize dead code.
    """
    for _ in range(max_iterations):
        unused_functions = search_unused_functions(program)
        if not unused_functions:
            return

        for function in unused_functions:
            program.functions.pop(function.name)
