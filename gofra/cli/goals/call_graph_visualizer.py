from __future__ import annotations

import sys
from enum import StrEnum
from typing import TYPE_CHECKING, Literal, NoReturn

from gofra.cli.goals._optimization_pipeline import cli_process_optimization_pipeline
from gofra.cli.output import cli_fatal_abort
from libgofra.gofra import process_input_file
from libgofra.lexer.tokens import TokenLocation
from libgofra.optimizer.helpers.call_graph import CallGraph, CallGraphNode, CallSite
from libgofra.preprocessor.macros.registry import registry_from_raw_definitions

if TYPE_CHECKING:
    from gofra.cli.parser.arguments import CLIArguments
    from libgofra.hir.function import Function


def cli_perform_call_graph_goal(args: CLIArguments) -> NoReturn:
    """Perform call graph display only goal that emits call graph graphviz dot format into stdout."""
    assert args.call_graph_only, (
        "Cannot perform call graph goal with no call graph flag set!"
    )
    assert not args.lexer_debug_emit_lexemes, "Try use compile goal"

    if args.output_file_is_specified:
        return cli_fatal_abort(
            text="Output file has no effect for call graph only goal, please pipe output via posix pipe (`>`) into desired file!",
        )

    if len(args.source_filepaths) > 1:
        return cli_fatal_abort(
            text="Multiple source files has not effect for call graph only goal, as it has no linkage, please specify single file!",
        )

    macros_registry = registry_from_raw_definitions(
        location=TokenLocation.cli(),
        definitions=args.definitions,
    ).inject_propagated_defaults(target=args.target)

    module = process_input_file(
        args.source_filepaths[0],
        args.include_paths,
        macros=macros_registry,
        rt_array_oob_check=args.runtime_array_oob_checks,
    )

    cli_process_optimization_pipeline(module, args)

    cg = CallGraph(module)
    dot_data = call_graph_to_dot_format(cg, module.entry_point_ref)
    print(dot_data)
    return sys.exit(0)


class DotNodeColor(StrEnum):
    DEFAULT = "white"
    ENTRY_POINT = "lightblue"
    UNUSED_FUNCTION = "lightgray"
    EXTERNAL = "bisque"


def call_graph_to_dot_format(
    call_graph: CallGraph,
    entry_point_ref: Function | None,
    *,
    digraph_name: str = "CallGraph",
) -> str:
    lines: list[str] = []
    lines.append("digraph %s {" % digraph_name)
    lines.append("  rankdir=LR;")
    lines.append('  node [shape=box, style=filled, fontname="Courier"];')
    lines.append('  edge [fontname="Courier", fontsize=10];')

    for node in call_graph.traverse_nodes():
        fillcolor = _get_node_color(node, entry_point_ref)
        style = _get_node_style(node)

        func = node.function
        label = (
            f"λ of {'$'.join(func.name.split('$')[:-1])}"
            if func.enclosed_in_parent
            else func.name
        )

        lines.append(
            f'  "{func.name}" [label="{label}", style="{style}", fillcolor="{fillcolor}"];',
        )

    for node in call_graph.traverse_nodes():
        for call_site in node.outgoing_edges:
            style = _get_call_edge_style(call_site)
            arrowhead = "empty" if call_site.callee.is_external else "normal"
            lines.append(
                f'  "{call_site.caller.name}" -> "{call_site.callee.name}" [style="{style}", arrowhead="{arrowhead}"];',
            )

    lines.append("}")
    return "\n".join(lines)


def _get_node_color(
    node: CallGraphNode,
    entry_point_ref: Function | None,
) -> DotNodeColor:
    if node.function == entry_point_ref:
        return DotNodeColor.ENTRY_POINT
    if node.is_root_node:
        return DotNodeColor.UNUSED_FUNCTION

    if node.function.is_external:
        return DotNodeColor.EXTERNAL
    return DotNodeColor.DEFAULT


def _get_node_style(node: CallGraphNode) -> Literal["filled", "dashed"]:
    _ = node
    if node.function.enclosed_in_parent:
        return "dashed"
    return "filled"


def _get_call_edge_style(call_site: CallSite) -> Literal["solid", "dashed"]:
    if call_site.is_address_obtain:
        return "dashed"
    assert call_site.is_direct_call
    return "solid"
