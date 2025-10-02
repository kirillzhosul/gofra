"""`pkg-config` wrapper for toolchain assembler (e.g linker mostly)."""

from shutil import which
from subprocess import DEVNULL, PIPE, run

from gofra.cli.output import cli_message


def get_pkg_config_libraries_linker_flags(
    library: str,
    *,
    verbose: bool = True,
) -> list[str] | None:
    """Get linker flags (e.g `--libs` yielding -l/-L flags) for given libraries using `pkg-config`."""
    if not which("pkg-config"):
        # `pkg-config` is not installed / misconfigured in system - cannot use that
        return None

    command = ["pkg-config", "--libs", library]
    cli_message(
        "INFO",
        f"Running pkg-config with `{' '.join(command)}` to obtain linker flags for library {library}",
        verbose=verbose,
    )
    process = run(
        command,
        check=False,
        stdout=PIPE,
        stderr=DEVNULL,
    )

    return process.stdout.decode().split()
