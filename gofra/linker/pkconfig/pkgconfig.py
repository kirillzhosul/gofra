from functools import lru_cache
from pathlib import Path
from shutil import which
from subprocess import DEVNULL, PIPE, run


@lru_cache(maxsize=128)
def pkgconfig_get_library_search_paths(
    library: str,
) -> list[Path] | None:
    """Get linker library search paths using `pkg-config` (e.g `--libs` yielding -l/-L flags) if it is installed in system."""
    if not which("pkg-config"):
        # `pkg-config` is not installed / misconfigured in system - cannot use that
        return None

    command = ("pkg-config", "--libs", library)
    process = run(
        command,
        check=False,
        stdout=PIPE,
        stderr=DEVNULL,
    )

    linker_flags = process.stdout.decode().split()
    return [
        Path(flag.removeprefix("-L")) for flag in linker_flags if flag.startswith("-L")
    ]
