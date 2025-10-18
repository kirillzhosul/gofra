import sys
from platform import platform, python_implementation, python_version
from typing import NoReturn

from gofra.cli.parser.arguments import CLIArguments


def cli_perform_version_goal(args: CLIArguments) -> NoReturn:
    """Perform version goal that display information about host and toolchain."""
    print("[Gofra toolchain]")
    print()
    print("Toolchain target (may be unavailable on host machine):")
    print(f"\tTriplet: {args.target.triplet}")
    print(f"\tArchitecture: {args.target.architecture}")
    print(f"\tOS: {args.target.operating_system}")
    print()
    print("Host machine:")
    print(f"\tPlatform: {platform()}")
    print(f"\tPython: {python_implementation()} {python_version()}")
    print()
    return sys.exit(0)
