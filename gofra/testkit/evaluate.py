import signal
import sys
from pathlib import Path
from subprocess import PIPE, CalledProcessError, TimeoutExpired

from gofra.cli.output import cli_linter_warning, cli_message
from gofra.execution.execution import execute_binary_executable
from gofra.execution.permissions import apply_file_executable_permissions
from libgofra.assembler.assembler import (
    assemble_object_from_codegen_assembly,
)
from libgofra.codegen.generator import generate_code_for_assembler
from libgofra.exceptions import GofraError
from libgofra.gofra import process_input_file
from libgofra.lexer.tokens import TokenLocation
from libgofra.linker.linker import link_object_files
from libgofra.linker.output_format import LinkerOutputFormat
from libgofra.linker.profile import LinkerProfile
from libgofra.preprocessor.macros import registry_from_raw_definitions
from libgofra.preprocessor.macros.defaults import (
    construct_propagated_toolchain_definitions,
)
from libgofra.preprocessor.macros.registry import MacrosRegistry
from libgofra.targets import Target
from libgofra.typecheck.typechecker import validate_type_safety

from .cli.arguments import CLIArguments
from .test import Test, TestStatus


def toolchain_assembly_executable(
    path: Path,
    args: CLIArguments,
    macros: MacrosRegistry,
    build_target: Target,
    cache_directory: Path,
) -> Path:
    module = process_input_file(
        path,
        include_paths=args.include_paths,
        macros=macros,
    )
    validate_type_safety(
        module,
        strict_expect_entry_point=True,
        on_lint_warning=cli_linter_warning,
    )
    artifact_path = cache_directory / f"{path.with_suffix('').name}"
    artifact_object_file = artifact_path.with_suffix(".o")
    artifact_assembly_file = artifact_path.with_suffix(".s")

    generate_code_for_assembler(
        artifact_assembly_file,
        module,
        build_target,
        on_warning=lambda text: cli_message(
            "WARNING",
            text=text,
            verbose=args.verbose,
        ),
    )
    assemble_object_from_codegen_assembly(
        assembly=artifact_assembly_file,
        output=artifact_object_file,
        debug_information=True,
        target=build_target,
        # Probably, at some time this may became configurable for more complex tests.
        additional_assembler_flags=[],
    )

    linker_process = link_object_files(
        objects=[artifact_object_file],
        target=build_target,
        output=artifact_path,
        libraries=[],
        output_format=LinkerOutputFormat.EXECUTABLE,
        additional_flags=[],
        libraries_search_paths=[],
        profile=LinkerProfile.DEBUG,
        cache_directory=cache_directory,
    )
    linker_process.check_returncode()
    return artifact_path


def evaluate_test_case(
    path: Path,
    args: CLIArguments,
    build_target: Target,
    cache_directory: Path,
) -> Test:
    definitions = construct_propagated_toolchain_definitions(target=build_target)

    macros = registry_from_raw_definitions(
        location=TokenLocation.toolchain(),
        definitions=definitions,
    )
    try:
        artifact_path = toolchain_assembly_executable(
            path,
            args,
            macros,
            build_target,
            cache_directory,
        )
    except GofraError as e:
        return Test(
            target=build_target,
            status=TestStatus.TOOLCHAIN_ERROR,
            path=path,
            error=e,
        )

    if args.build_only_no_execute:
        return Test(
            target=build_target,
            status=TestStatus.SUCCESS,
            path=path,
            artifact_path=artifact_path,
        )

    expected_exit_code_macro = macros.get("TESTKIT_EXPECTED_EXIT_CODE")
    expected_exit_code = (
        0 if not expected_exit_code_macro else expected_exit_code_macro.tokens[0].value
    )

    if expected_exit_code in (-signal.SIGSEGV, signal.SIGSEGV, 128 + signal.SIGSEGV):
        cli_message(
            "WARNING",
            f"Expected exit code is equals to SIGSEGV signal ({expected_exit_code}) this may cause invalid error messages when testing",
        )

    if not isinstance(expected_exit_code, int):
        msg = "Expected TESTKIT_EXPECTED_EXIT_CODE to be an integer."
        raise TypeError(msg)

    apply_file_executable_permissions(filepath=artifact_path)

    try:
        exit_code = execute_binary_executable(
            artifact_path,
            args=[],
            timeout=15,
            stdout=PIPE,
            stderr=PIPE,
            stdin=PIPE,
        )
    except TimeoutExpired as e:
        return Test(
            target=build_target,
            status=TestStatus.EXECUTION_TIMEOUT_ERROR,
            path=path,
            artifact_path=artifact_path,
            error=e,
        )
    except KeyboardInterrupt:
        cli_message("WARNING", "Testkit execution was interrupted by user!")
        sys.exit(0)

    if exit_code != expected_exit_code:
        return Test(
            target=build_target,
            status=TestStatus.EXECUTION_STATUS_ERROR,
            expected_exit_code=expected_exit_code,
            path=path,
            artifact_path=artifact_path,
            error=CalledProcessError(returncode=exit_code, cmd=artifact_path),
        )

    return Test(
        target=build_target,
        status=TestStatus.SUCCESS,
        path=path,
        artifact_path=artifact_path,
        expected_exit_code=expected_exit_code,
    )
