from pathlib import Path


def prepare_build_cache_directory(build_cache_directory: Path) -> None:
    """Try to create and fill cache directory with required files."""
    if build_cache_directory.exists():
        return

    build_cache_directory.mkdir(exist_ok=False)

    with (build_cache_directory / ".gitignore").open("w") as f:
        f.write("# Do not include this newly generated build cache into git VCS\n")
        f.write("*\n")
