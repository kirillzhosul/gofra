import sys
from pathlib import Path
from subprocess import CalledProcessError, TimeoutExpired

from gofra.assembler.assembler import OUTPUT_FORMAT_T, assemble_program
from gofra.cli.definitions import construct_propagated_toolchain_definitions
from gofra.cli.output import cli_message
from gofra.consts import GOFRA_ENTRY_POINT
from gofra.exceptions import GofraError
from gofra.execution.execution import execute_binary_executable
from gofra.execution.permissions import apply_file_executable_permissions
from gofra.gofra import process_input_file
from gofra.lexer.tokens import TokenLocation
from gofra.linker.linker import link_object_files
from gofra.linker.output_format import LinkerOutputFormat
from gofra.linker.profile import LinkerProfile
from gofra.preprocessor.macros import registry_from_raw_definitions
from gofra.preprocessor.macros.registry import MacrosRegistry
from gofra.targets import Target
from gofra.typecheck.typechecker import validate_type_safety

from .cli.arguments import CLIArguments
from .test import Test, TestStatus


def toolchain_assembly_executable(
    path: Path,
    args: CLIArguments,
    macros: MacrosRegistry,
    build_target: Target,
    cache_directory: Path,
    build_format: OUTPUT_FORMAT_T,
) -> Path:
    context = process_input_file(
        path,
        include_paths=args.include_paths,
        macros=macros,
    )
    validate_type_safety(
        functions={**context.functions, GOFRA_ENTRY_POINT: context.entry_point},
    )
    artifact_path = cache_directory / f"{path.with_suffix('').name}"
    objects = assemble_program(
        context,
        artifact_path,
        output_format=build_format,
        target=build_target,
        verbose=args.verbose,
        # Probably, at some time this may became configurable for more complex tests.
        additional_assembler_flags=[],
        # Artifacts removed by top level, here we delete only build cache.
        delete_build_cache_after_compilation=args.delete_build_cache,
        build_cache_dir=cache_directory,
    )
    assert objects
    linker_proccess = link_object_files(
        objects=objects,
        target=build_target,
        output=artifact_path,
        libraries=[],
        output_format=LinkerOutputFormat.EXECUTABLE,
        additional_flags=[],
        libraries_search_paths=[],
        profile=LinkerProfile.DEBUG,
        cache_directory=cache_directory,
    )
    linker_proccess.check_returncode()
    return artifact_path


def evaluate_test_case(
    path: Path,
    args: CLIArguments,
    build_target: Target,
    build_format: OUTPUT_FORMAT_T,
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
            build_format,
        )
    except GofraError as e:
        return Test(
            target=build_target,
            status=TestStatus.TOOLCHAIN_ERROR,
            path=path,
            error=e,
        )

    expected_exit_code_macro = macros.get("TESTKIT_EXPECTED_EXIT_CODE")
    expected_exit_code = (
        0 if not expected_exit_code_macro else expected_exit_code_macro.tokens[0].value
    )

    if not isinstance(expected_exit_code, int):
        msg = "Expected TESTKIT_EXPECTED_EXIT_CODE to be an integer."
        raise TypeError(msg)

    apply_file_executable_permissions(filepath=artifact_path)

    try:
        exit_code = execute_binary_executable(artifact_path, args=[], timeout=15)
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
