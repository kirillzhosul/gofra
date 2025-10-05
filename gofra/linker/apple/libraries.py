from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from subprocess import run

from gofra.linker.apple.output_format import AppleLinkerOutputFormat

# By default system library root is located here (`xcrun -sdk macosx --show-sdk-path`)
SYSLIBROOT_DEFAULT_PATH = Path("/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk")
SYSLIBROOT_XCRUN_GET_COMMAND = ["/usr/bin/xcrun", "-sdk", "macosx", "--show-sdk-path"]

# We use explicit `-Z` flag so we explicitly propagate these search paths.
APPLE_LINKER_DEFAULT_LIBRARIES_SEARCH_PATHS = [
    Path("/usr/lib"),
    Path("/usr/local/lib"),
]


@lru_cache(maxsize=1)
def get_syslibroot_path() -> Path:
    """Get `syslibroot` path flag for linker. Do not call `xcrun` multiple times."""
    if SYSLIBROOT_DEFAULT_PATH.exists():
        return SYSLIBROOT_DEFAULT_PATH

    # TODO(@kirillzhosul): Add logging about performing `SYSLIBROOT_XCRUN_GET_COMMAND`

    process = run(SYSLIBROOT_XCRUN_GET_COMMAND, check=False)
    process.check_returncode()

    return Path(process.stdout.decode().strip())


def syslibroot_is_requred(
    libraries: Iterable[str],
    output_format: AppleLinkerOutputFormat,
) -> bool:
    return "System" in libraries or output_format == AppleLinkerOutputFormat.EXECUTABLE
