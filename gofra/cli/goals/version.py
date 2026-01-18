import sys
from platform import platform, python_implementation, python_version
from typing import NoReturn

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

    return sys.exit(0)
