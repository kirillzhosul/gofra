from argparse import ArgumentParser

from gofra.cli.parser import groups


def build_cli_parser(prog: str) -> ArgumentParser:
    """Get argument parser instance to parse incoming arguments."""
    parser = ArgumentParser(
        description="Gofra Toolkit - CLI for working with Gofra programming language",
        usage=f"{prog} files... [options] [-h]",
        add_help=True,
        allow_abbrev=False,
        prog=prog,
    )

    parser.add_argument(
        "source_files",
        help="Input source code files in Gofra to process (`.gof` files)",
        nargs="*",
        default=[],
    )

    parser.add_argument(
        "--version",
        default=False,
        action="store_true",
        help="Show version info",
    )

    parser.add_argument(
        "--repl",
        default=False,
        action="store_true",
        help="Step into REPL",
    )

    groups.add_target_group(parser)
    groups.add_output_group(parser)
    groups.add_logging_group(parser)

    groups.add_debug_group(parser)
    groups.add_preprocessor_group(parser)
    groups.add_cache_group(parser)
    groups.add_linker_group(parser)
    groups.add_optimizer_group(parser)
    groups.add_toolchain_debug_group(parser)
    groups.add_codegen_group(parser)
    groups.add_additional_group(parser)
    return parser
