import sys

from gofra.cli.errors import cli_gofra_error_handler
from gofra.cli.infer import infer_target
from gofra.cli.output import cli_message
from gofra.linker.cli.arguments import parse_cli_arguments
from gofra.linker.linker import link_object_files
from gofra.linker.output_format import LinkerOutputFormat
from gofra.linker.profile import LinkerProfile


def cli_entry_point() -> None:
    """CLI main entry."""
    with cli_gofra_error_handler():
        args = parse_cli_arguments()

        linker_process = link_object_files(
            objects=args.files,
            target=infer_target(),
            output=args.output,
            libraries=[],
            output_format=LinkerOutputFormat.EXECUTABLE,
            additional_flags=[],
            libraries_search_paths=[],
            profile=LinkerProfile.DEBUG,
            executable_entry_point_symbol=args.executable_entry_point_symbol,
            cache_directory=None,
        )
        if linker_process.returncode != 0:
            cli_message(
                "ERROR",
                f"Linker process failed with exit code {linker_process.returncode}!",
            )
            sys.exit(linker_process.returncode)
