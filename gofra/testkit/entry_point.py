from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING

from gofra.assembler.assembler import assemble_program
from gofra.cli.errors import cli_gofra_error_handler
from gofra.cli.output import CLIColor, cli_message
from gofra.exceptions import GofraError
from gofra.gofra import process_input_file

from .arguments import CLIArguments, parse_cli_arguments

if TYPE_CHECKING:
    from collections.abc import Generator


class TestStatus(Enum):
    SKIPPED = auto()

    ERROR = auto()
    SUCCESS = auto()


@dataclass(frozen=False)
class Test:
    status: TestStatus
    path: Path
    error: GofraError | None = None


COLORS = {
    TestStatus.SUCCESS: CLIColor.GREEN,
    TestStatus.ERROR: CLIColor.RED,
    TestStatus.SKIPPED: CLIColor.RESET,
}
ICONS = {
    TestStatus.SUCCESS: "+",
    TestStatus.ERROR: "-",
    TestStatus.SKIPPED: ".",
}


def cli_entry_point() -> None:
    """CLI main entry."""
    with cli_gofra_error_handler():
        args = parse_cli_arguments()
        cli_process_testkit_runner(args)


def cli_process_testkit_runner(args: CLIArguments) -> None:
    """Process full testkit toolchain."""
    cli_message(level="INFO", text="Searching test files...")

    test_paths = tuple(search_test_case_files(args.directory))
    cli_message(
        level="INFO",
        text=f"Found {len(test_paths)} test case files.",
    )

    test_matrix: list[Test] = []
    for test_path in test_paths:
        try:
            context = process_input_file(filepath=test_path, include_paths=[])
        except GofraError as e:
            test_matrix.append(Test(status=TestStatus.ERROR, path=test_path, error=e))
            continue
        assemble_program(
            context,
            Path(
                args.build_cache_dir
                / f"._testkit__build__{test_path.with_suffix('').name}",
            ),
            output_format="executable",
            target="aarch64-darwin",
            build_cache_dir=args.build_cache_dir,
            verbose=True,
            additional_assembler_flags=[],
            additional_linker_flags=[],
            delete_build_cache_after_compilation=True,
        )
        test_matrix.append(Test(status=TestStatus.SUCCESS, path=test_path))
    display_test_matrix(test_matrix)
    display_test_errors(test_matrix)


def search_test_case_files(directory: Path) -> Generator[Path]:
    return directory.glob("test_*.gof", case_sensitive=False)


def display_test_matrix(matrix: list[Test]) -> None:
    for test in matrix:
        color = COLORS[test.status]
        icon = ICONS[test.status]
        print(f"{color}{icon}", test.path)


def display_test_errors(matrix: list[Test]) -> None:
    if any(test.error for test in matrix):
        cli_message("ERROR", "While running tests, some errors were occured:")
    for test in matrix:
        if test.error is None:
            continue
        cli_message("INFO", f"While testing `{test.path}`:")
        cli_message("ERROR", repr(test.error))
