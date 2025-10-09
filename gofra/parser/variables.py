from gofra.hir.variable import Variable
from gofra.parser._context import ParserContext


def search_variable_in_context_parents(
    child: ParserContext,
    variable: str,
) -> Variable | None:
    context_ref = child

    while True:
        if variable in context_ref.variables:
            return context_ref.variables[variable]

        if context_ref.parent:
            context_ref = context_ref.parent
            continue

        return None


def get_all_scopes_variables(
    child: ParserContext,
) -> list[Variable]:
    context_ref = child
    variables: list[Variable] = []
    while True:
        variables.extend(context_ref.variables.values())

        if context_ref.parent:
            context_ref = context_ref.parent
            continue

        return variables
