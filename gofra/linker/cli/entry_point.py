import sys

from gofra.cli.errors import cli_gofra_error_handler
from gofra.cli.output import cli_message
from gofra.linker.apple.command_composer import compose_apple_linker_command
from gofra.linker.cli.arguments import parse_cli_arguments
from gofra.linker.command_composer import get_linker_command_composer_backend
from gofra.linker.gnu.command_composer import compose_gnu_linker_command
from gofra.linker.linker import link_object_files


def cli_entry_point() -> None:
    """CLI main entry."""
    with cli_gofra_error_handler():
        args = parse_cli_arguments()

        if args.linker_backend is None:
            linker_backend = get_linker_command_composer_backend(args.target)
        else:
            match args.linker_backend:
                case "apple-ld":
                    linker_backend = compose_apple_linker_command
                case "gnu-ld":
                    linker_backend = compose_gnu_linker_command

        linker_process = link_object_files(
            objects=args.files,
            target=args.target,
            output=args.output,
            libraries=args.libraries,
            output_format=args.output_format,
            additional_flags=args.additional_flags,
            libraries_search_paths=args.libraries_search_paths,
            profile=args.profile,
            executable_entry_point_symbol=args.executable_entry_point_symbol,
            cache_directory=None,
            linker_backend=linker_backend,
        )
        if linker_process.returncode != 0:
            cli_message(
                "ERROR",
                f"Linker process failed with exit code {linker_process.returncode}!",
            )
            sys.exit(linker_process.returncode)
