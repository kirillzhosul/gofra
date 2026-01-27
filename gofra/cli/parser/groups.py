import argparse
from argparse import ArgumentParser


def add_debug_group(parser: ArgumentParser) -> None:
    """Construct and inject argument group with debug options into given parser."""
    group = parser.add_argument_group("Debug", "Debugging and IR inspection")

    group.add_argument(
        "-hir",
        required=False,
        action="store_true",
        help="If passed will just emit IR (high-level) of provided file(s) into stdin.",
    )

    group.add_argument(
        "--debug-symbols",
        "-g",
        required=False,
        action="store_true",
        help="If passed will provide debug symbols into final target output.",
    )

    cfi_group = group.add_mutually_exclusive_group()
    cfi_group.add_argument(
        "--no-dwarf-cfi",
        action="store_false",
        dest="codegen_emit_dwarf_cfi",
        help="Disable DWARF CFI generation",
    )
    cfi_group.add_argument(
        "--always-dwarf-cfi",
        action="store_true",
        dest="codegen_emit_dwarf_cfi",
        help="Always enable DWARF CFI generation",
    )
    group.set_defaults(codegen_emit_dwarf_cfi=None)

    group.add_argument(
        "--verbose",
        "-v",
        required=False,
        action="store_true",
        help="If passed will enable INFO level logs from compiler.",
    )

    group.add_argument(
        "-vv",
        "-###",
        required=False,
        dest="show_commands",
        action="store_true",
        help="If passed will display commands that compiler performed if any.",
    )

    group.add_argument(
        "--no-lint",
        "--no-lint-warnings",
        dest="display_lint_warnings",
        action="store_false",
        default=True,
        required=False,
        help="If passed, will hide linter warnings (e.g unused functions and etc)",
    )


def add_additional_group(parser: ArgumentParser) -> None:
    """Construct and inject argument group with extra options that does not hits any existent group into given parser."""
    group = parser.add_argument_group("Additional", "Extra flags")
    group.add_argument(
        "--assembler",
        "-Af",
        required=False,
        help="Additional flags passed to assembler (`as`)",
        action="append",
        nargs="?",
        default=[],
    )
    group.add_argument(
        "--rt-bounds-checks",
        "--oob-checks",
        action="store_true",
        default=False,
        dest="runtime_array_oob_checks",
        required=False,
        help="If passed, will enable injecting Out-Of-Bounds (OOB) checks into runtime when accessing arrays(!), WIP feature that must be treated as feature flag",
    )

    group.add_argument(
        "--skip-typecheck",
        "-nt",
        action="store_true",
        required=False,
        help="If passed, will disable type safety checking",
    )


def add_toolchain_debug_group(parser: ArgumentParser) -> None:
    """Construct and inject argument group with internal toolchain debug options into given parser."""
    parser.add_argument(
        "--debug-emit-lexemes",
        dest="lexer_debug_emit_lexemes",
        action="store_true",
        help=argparse.SUPPRESS,
    )

    parser.add_argument(
        "--debug-unwrap-errors",
        dest="cli_debug_user_friendly_errors",
        action="store_false",
        default=True,
        help=argparse.SUPPRESS,
    )


def add_target_group(parser: ArgumentParser) -> None:
    """Construct and inject argument group with target options into given parser."""
    group = parser.add_argument_group("Target", "Compilation target configuration")
    group.add_argument(
        "--target",
        "-t",
        type=str,
        required=False,
        help="Target compilation triplet. By default target is inferred from host system. Cross-compilation is not supported so that argument is a bit odd and cannot properly be used.",
        choices=[
            # Triplets
            "amd64-unknown-linux",
            "arm64-apple-darwin",
            "amd64-unknown-windows",
            "wasm32-unknown-none",
            # Shortcuts
            "wasm",
        ],
    )


def add_output_group(parser: ArgumentParser) -> None:
    """Construct and inject argument group with output options into given parser."""
    group = parser.add_argument_group("Output", "Control compilation output")
    group.add_argument(
        "--output",
        "-o",
        type=str,
        required=False,
        help="Output file path to generate, by default will be inferred from first input filename",
    )
    group.add_argument(
        "--output-format",
        "-of",
        type=str,
        required=False,
        help="Compilation output format. Useful if you want to emit '.o' object-file.",
        default="executable",
        choices=["object", "executable", "library", "assembly"],
    )

    group.add_argument(
        "--execute",
        "-x",
        required=False,
        action="store_true",
        help="If provided, will execute output executable file after compilation. Expects output format to be executable",
    )


def add_preprocessor_group(parser: ArgumentParser) -> None:
    """Construct and inject argument group with preprocessor options into given parser."""
    group = parser.add_argument_group(
        title="Preprocessor",
        description="Flags for the preprocessor.",
    )
    group.add_argument(
        "--preprocess-only",
        "--pp",
        "-P",
        default=False,
        action="store_true",
        help="If passed will emit preprocessed text of an source into stdout",
    )
    group.add_argument(
        "--include",
        "-i",
        required=False,
        help="Additional directories to search for include files.",
        action="append",
        default=[],
    )
    group.add_argument(
        "--define",
        "-D",
        required=False,
        help="Define an macro (default value is '1') and propagate to all input source files",
        action="append",
        nargs="?",
        dest="definitions",
        default=[],
    )


def add_cache_group(parser: ArgumentParser) -> None:
    """Construct and inject argument group with cache options into given parser."""
    group = parser.add_argument_group(
        title="Cache",
        description="Build cache and artifacts (incremental compilation)",
    )

    group.add_argument(
        "--incremental",
        dest="incremental_compilation",
        default=False,
        action="store_true",
        required=False,
        help="If passed, enables incremental compilation with rebuilding only modified artifacts",
    )

    group.add_argument(
        "--cache-dir",
        "-cd",
        type=str,
        default="./.build",
        required=False,
        help="Path to directory where to store cache (defaults to `./.build`)",
    )

    group.add_argument(
        "--delete-cache",
        "-dc",
        action="store_true",
        required=False,
        help="If passed, will delete cache after run (excludes final build artifact)",
    )


def add_linker_group(parser: ArgumentParser) -> None:
    """Construct and inject argument group with linker options into given parser."""
    group = parser.add_argument_group(
        title="Linker",
        description="Flags for the linker, fine control how linker links your objects.",
    )

    group.add_argument(
        "--library-search-path",
        "-L",
        dest="linker_libraries_search_paths",
        required=False,
        help="Paths where to search for linker libraries",
        action="append",
        nargs="?",
        default=[],
    )

    group.add_argument(
        "--linker-profile",
        dest="linker_profile",
        required=False,
        default="debug",
        choices=["debug", "production"],
        help="Configures some underlying linker tools to use that profile. Default to DEBUG",
    )

    group.add_argument(
        "--linker-flag",
        "-alf",
        dest="linker_additional_flags",
        required=False,
        help="Additional flags passed to specified linker",
        action="append",
        default=[],
    )

    group.add_argument(
        "--no-pkgconfig",
        dest="linker_resolve_libraries_with_pkgconfig",
        default=True,
        action="store_false",
        help="Disable usage of `pkg-config` to resolve linker search paths if possible",
    )
    group.add_argument(
        "--library",
        "--lib",
        "-l",
        dest="linker_libraries",
        required=False,
        help="Libraries against which to link",
        action="append",
        nargs="?",
        default=[],
    )

    group.add_argument(
        "--linker-backend",
        type=str,
        required=False,
        default=None,
        dest="linker_backend",
        help="Linker backend to use (e.g linker)",
        choices=["gnu-ld", "apple-ld"],
    )

    group.add_argument(
        "--linker-executable",
        type=str,
        required=False,
        default=None,
        dest="linker_executable",
        help="Linker backend executable path to use",
    )


def add_optimizer_group(parser: ArgumentParser) -> None:
    """Construct and inject argument group with optimizer options into given parser."""
    group = parser.add_argument_group(
        title="Optimizations",
        description="Flags for the optimizer, fine control how compiler optimize your code.",
    )

    ###
    # Optimization level.
    ###
    group_optimization_level = group.add_mutually_exclusive_group(required=False)
    group_optimization_level.add_argument(
        "-O0",
        dest="optimizer_level",
        action="store_const",
        default=0,
        const=0,
        help="Disable all optimizations (default).",
    )
    group_optimization_level.add_argument(
        "-O1",
        dest="optimizer_level",
        action="store_const",
        const=1,
        help="Apply basic optimizations.",
    )

    ###
    # DCE (dead-code-elimination).
    ###
    group_dce = group.add_mutually_exclusive_group(required=False)
    group_dce.add_argument(
        "-fdce",
        dest="optimizer_do_dead_code_elimination",
        action="store_const",
        const=True,
        help="[Enabled at -O1 and above] Force enable DCE (dead-code-elimination) optimization. Removes unused functions (no calls to them inside final program), except explicit 'public' ones.",
    )
    group_dce.add_argument(
        "-fno-dce",
        action="store_const",
        const=False,
        dest="optimizer_do_dead_code_elimination",
        help="[Enabled at -O1 and above] Force disable DCE (dead-code-elimination) optimization, see '-fdce' flag for more information.",
    )
    group_dce.add_argument(
        "--dce-max-iterations",
        metavar="<N>",
        dest="optimizer_dead_code_elimination_max_iterations",
        help="Max iterations limit for DCE optimization. Low limit may result into not all functions are being removed due to their reference to each in cascade.",
    )

    ###
    # Function inlining
    ###
    group_inline = group.add_mutually_exclusive_group()
    group_inline.add_argument(
        "-finline-functions",
        dest="optimizer_do_function_inlining",
        action="store_const",
        const=True,
        help="[Enabled at -O1 and above] Force enable function inlining optimization. Marks small functions as 'inline' (size is controlled with '--inline-functions-threshold') to reduce function overhead.",
    )
    group_inline.add_argument(
        "-fno-inline-functions",
        action="store_const",
        const=False,
        dest="optimizer_do_function_inlining",
        help="[Enabled at -O1 and above] Force disable function inlining optimization, see '-finline-functions' flag for more information.",
    )
    group_inline.add_argument(
        "--inline-functions-max-operators",
        metavar="<N>",
        dest="optimizer_function_inlining_max_operators",
        help="Max size of an function to be inlined with function inlining optimization in operators",
    )
    group_inline.add_argument(
        "--inline-functions-max-iterations",
        metavar="<N>",
        dest="optimizer_function_inlining_max_iterations",
        help="Max iterations for function inlining to search for new inlined function usage in other functions. Low limit will result into unknown function call at assembler stage. This may slightly increase final binary size",
    )
