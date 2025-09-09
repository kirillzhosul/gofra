import sys
from pathlib import Path
from subprocess import CalledProcessError, TimeoutExpired, run

from gofra.assembler.assembler import OUTPUT_FORMAT_T, assemble_program
from gofra.cli.definitions import construct_propagated_toolchain_definitions
from gofra.cli.entry_point import PERMISSION_CHMOD_EXECUTABLE
from gofra.cli.output import cli_message
from gofra.codegen.targets import TARGET_T
from gofra.consts import GOFRA_ENTRY_POINT
from gofra.exceptions import GofraError
from gofra.gofra import process_input_file
from gofra.typecheck.typechecker import validate_type_safety

from .cli.arguments import CLIArguments
from .test import Test, TestStatus


def evaluate_test_case(
    path: Path,
    args: CLIArguments,
    build_target: TARGET_T,
    build_format: OUTPUT_FORMAT_T,
    cache_directory: Path,
) -> Test:
    definitions = construct_propagated_toolchain_definitions(
        build_target_triplet=build_target,
    )

    try:
        context = process_input_file(
            path,
            include_paths=args.include_paths,
            propagated_definitions=definitions,
        )
        validate_type_safety(
            functions={**context.functions, GOFRA_ENTRY_POINT: context.entry_point},
        )
        artifact_path = cache_directory / f"{path.with_suffix('').name}"
        assemble_program(
            context,
            artifact_path,
            output_format=build_format,
            target=build_target,
            verbose=args.verbose,
            # Probably, at some time this may became configurable for more complex tests.
            additional_assembler_flags=[],
            additional_linker_flags=[],
            # This must not fail, and generally will just decrease binary size
            # which is not reasonable for testkit.
            link_with_system_libraries=True,
            # Artifacts removed by top level, here we delete only build cache.
            delete_build_cache_after_compilation=args.delete_build_cache,
            build_cache_dir=cache_directory,
        )
    except GofraError as e:
        return Test(
            target=build_target,
            status=TestStatus.TOOLCHAIN_ERROR,
            path=path,
            error=e,
        )

    assert artifact_path.exists()
    artifact_path.chmod(PERMISSION_CHMOD_EXECUTABLE)

    try:
        run(  # noqa: S602
            [artifact_path.absolute()],
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
            check=True,
            shell=True,
            timeout=15,
        )
    except CalledProcessError as e:
        return Test(
            target=build_target,
            status=TestStatus.EXECUTION_ERROR,
            path=path,
            artifact_path=artifact_path,
            error=e,
        )
    except TimeoutExpired as e:
        return Test(
            target=build_target,
            status=TestStatus.EXECUTION_ERROR,
            path=path,
            artifact_path=artifact_path,
            error=e,
        )
    except KeyboardInterrupt:
        cli_message("WARNING", "Testkit execution was interrupted by user!")
        sys.exit(0)

    return Test(
        target=build_target,
        status=TestStatus.SUCCESS,
        path=path,
        artifact_path=artifact_path,
    )
