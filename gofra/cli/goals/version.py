import sys
from platform import platform, python_implementation, python_version
from typing import Literal, NoReturn

from gofra.cli.parser.arguments import CLIArguments
from libgofra.assembler.drivers._get_assembler_driver import get_assembler_driver
from libgofra.feature_flags import (
    FEATURE_ALLOW_FPU,
    FEATURE_ALLOW_MODULES,
)
from libgofra.linker.command_composer import get_linker_command_composer_backend


def cli_perform_version_goal(args: CLIArguments) -> NoReturn:
    """Perform version goal that display information about host and toolchain."""
    linker_composer_backend = (
        get_linker_command_composer_backend(args.target)
        .__qualname__.removeprefix("compose_")
        .removesuffix("_command")
    )

    assembler_driver = get_assembler_driver(args.target)
    assembler_driver_name = assembler_driver.name if assembler_driver else "No suitable"

    print("[Gofra toolchain]")
    print("Toolchain target (may be unavailable on host machine):")
    print(f"\tTriplet: {args.target.triplet}")
    print(f"\tArchitecture: {args.target.architecture}")
    print(f"\tOS: {args.target.operating_system}")

    print("Tools and steps:")
    print(f"\tLinker backend: {linker_composer_backend}")
    print(f"\tAssembler driver: {assembler_driver_name}")

    print("Host machine:")
    print(f"\tPlatform: {platform()}")
    print(f"\tPython: {python_implementation()} {python_version()}")

    print("Features:")
    print(f"\tFEATURE_ALLOW_FPU = {FEATURE_ALLOW_FPU}")
    print(f"\tFEATURE_ALLOW_MODULES = {FEATURE_ALLOW_MODULES}")

    if args.verbose:
        print("[Internal settings]")
        print("\t[Include paths]:")
        for p in args.include_paths:
            print(f"\t - {p}")
        print()

        c = args.optimizer
        print("[Optimizer Config]:")
        print("\tDCE:", _switch_flag(c.do_dead_code_elimination))
        print(
            "\tDCE aggressive from entry point:",
            _switch_flag(c.dead_code_aggressive_from_entry_point),
        )
        print("\tFunction Inlining:", _switch_flag(c.do_function_inlining))
        print("\t... compiler heuristic ...")
        print()

        c = args.codegen_config
        print("[Codegen Config]:")
        print("\tNo compiler comments:", _switch_flag(c.no_compiler_comments))
        print("\tSystem entry point:", f'"{c.system_entry_point_name}"')
        print("\t[Optimizations]")
        print("\t - Align functions bytes:", c.align_functions_bytes or "no")
        print("\t - Peephole ISA:", _switch_flag(c.peephole_isa_optimizer))
        print(
            "\t - Omit unused frame pointers:",
            _switch_flag(c.omit_unused_frame_pointers),
        )
        print("\t[DWARF]")
        print("\t - CFI:", _switch_flag(c.dwarf_emit_cfi))
        print("\t - DIEs:", _switch_flag(c.dwarf_emit_dies))
        print("\t - Locations:", _switch_flag(c.dwarf_emit_locations))

    return sys.exit(0)


def _switch_flag(b: bool) -> Literal["on", "off"]:  # noqa: FBT001
    return "on" if b else "off"
