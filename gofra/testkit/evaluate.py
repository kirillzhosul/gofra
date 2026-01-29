import sys
from pathlib import Path
from subprocess import PIPE, CalledProcessError, TimeoutExpired

from gofra.cli.is_segmentation_fault import is_segmentation_fault
from gofra.cli.output import cli_linter_warning, cli_message
from gofra.execution.execution import execute_native_binary_executable
from gofra.execution.permissions import apply_file_executable_permissions
from libgofra.assembler.assembler import (
    assemble_object_file,
)
from libgofra.codegen.generator import generate_code_for_assembler
from libgofra.exceptions import GofraError
from libgofra.gofra import process_input_file
from libgofra.hir.module import Module
from libgofra.lexer.tokens import TokenType
from libgofra.linker.entry_point import LINKER_EXPECTED_ENTRY_POINT
from libgofra.linker.linker import link_object_files
from libgofra.linker.output_format import LinkerOutputFormat
from libgofra.linker.profile import LinkerProfile
from libgofra.preprocessor.macros.registry import MacrosRegistry
from libgofra.targets import Target
from libgofra.typecheck.typechecker import validate_type_safety

from .cli.arguments import CLIArguments
from .test import Test, TestStatus


def toolchain_assemble_executable(
    path: Path,
    module: Module,
    args: CLIArguments,
    build_target: Target,
    cache_directory: Path,
) -> Path:
    artifact_path = cache_directory / f"{path.with_suffix('').name}"
    artifact_object_file = artifact_path.with_suffix(".o")
    artifact_assembly_file = artifact_path.with_suffix(".s")

    generate_code_for_assembler(
        artifact_assembly_file,
        module,
        build_target,
        config=None,
        on_warning=lambda text: cli_message(
            "WARNING",
            text=text,
            verbose=args.verbose,
        ),
    )
    assemble_object_file(
        in_assembly_file=artifact_assembly_file,
        out_object_file=artifact_object_file,
        debug_information=True,
        target=build_target,
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
        executable_entry_point_symbol=LINKER_EXPECTED_ENTRY_POINT,
    )
    linker_process.check_returncode()
    return artifact_path


def evaluate_test_case(
    path: Path,
    args: CLIArguments,
    build_target: Target,
    cache_directory: Path,
    immutable_macros: MacrosRegistry,
) -> Test:
    macros = immutable_macros.copy()
    try:
        module = process_input_file(
            path,
            include_paths=args.include_paths,
            macros=macros,
        )
        assert not module.dependencies, "not implemented"
        validate_type_safety(
            module,
            strict_expect_entry_point=True,
            on_lint_warning=cli_linter_warning,
        )

        artifact_path = toolchain_assemble_executable(
            path,
            module,
            args,
            build_target,
            cache_directory,
        )
    except GofraError as e:
        expected_compile_error = _extract_expected_compile_error(macros)
        if expected_compile_error:
            if expected_compile_error in repr(e):
                # Got expected error
                return Test(
                    target=build_target,
                    status=TestStatus.SUCCESS,
                    path=path,
                    error=e,
                    expected_error=expected_compile_error,
                )
            # Expected one error but got another
            return Test(
                target=build_target,
                status=TestStatus.TOOLCHAIN_ERROR,
                path=path,
                error=e,
                expected_error=expected_compile_error,
            )
        # Error while not expected
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

    expected_compile_error = _extract_expected_compile_error(macros)
    if expected_compile_error:
        # Error while not expected
        return Test(
            target=build_target,
            status=TestStatus.EXPECTED_TOOLCHAIN_ERROR,
            path=path,
            expected_error=expected_compile_error,
        )

    expected_exit_code_macro = macros.get("TESTKIT_EXPECTED_EXIT_CODE")
    expected_exit_code = (
        0 if not expected_exit_code_macro else expected_exit_code_macro.tokens[0].value
    )

    if isinstance(expected_exit_code, int) and is_segmentation_fault(
        expected_exit_code,
    ):
        cli_message(
            "WARNING",
            f"Expected exit code is equals to SIGSEGV signal ({expected_exit_code}) this may cause invalid error messages when testing",
        )

    if not isinstance(expected_exit_code, int):
        msg = "Expected TESTKIT_EXPECTED_EXIT_CODE to be an integer."
        raise TypeError(msg)

    apply_file_executable_permissions(filepath=artifact_path)

    try:
        exit_code = execute_native_binary_executable(
            artifact_path,
            args=[],
            timeout=15,
            stdout=PIPE,
            stderr=PIPE,
            stdin=PIPE,
        ).returncode
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


def _extract_expected_compile_error(macros: MacrosRegistry) -> str | None:
    if "TESTKIT_EXPECT_COMPILE_ERROR" in macros:
        _value_token = macros["TESTKIT_EXPECT_COMPILE_ERROR"]

        assert _value_token.tokens
        assert _value_token.tokens[0].type == TokenType.STRING
        expected_compile_error = _value_token.tokens[0].value
        assert isinstance(expected_compile_error, str)
        assert expected_compile_error
        return expected_compile_error
    return None
