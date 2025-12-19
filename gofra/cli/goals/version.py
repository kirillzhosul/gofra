import sys
from platform import platform, python_implementation, python_version
from typing import NoReturn

from gofra.cli.parser.arguments import CLIArguments
from gofra.feature_flags import (
    FEATURE_ALLOW_FPU,
    FEATURE_RUNTIME_ARRAY_OOB_CHECKS,
)
from gofra.linker.command_composer import get_linker_command_composer_backend


def cli_perform_version_goal(args: CLIArguments) -> NoReturn:
    """Perform version goal that display information about host and toolchain."""
    linker_composer_backend = (
        get_linker_command_composer_backend(args.target)
        .__qualname__.removeprefix("compose_")
        .removesuffix("_command")
    )

    print("[Gofra toolchain]")
    print("Toolchain target (may be unavailable on host machine):")
    print(f"\tTriplet: {args.target.triplet}")
    print(f"\tArchitecture: {args.target.architecture}")
    print(f"\tOS: {args.target.operating_system}")
    print(f"\t(linker command composer: {linker_composer_backend})")
    print("Host machine:")
    print(f"\tPlatform: {platform()}")
    print(f"\tPython: {python_implementation()} {python_version()}")
    print("Features:")
    print(f"\tFEATURE_ALLOW_FPU = {FEATURE_ALLOW_FPU}")
    print(f"\tFEATURE_RUNTIME_ARRAY_OOB_CHECKS = {FEATURE_RUNTIME_ARRAY_OOB_CHECKS}")
    return sys.exit(0)
