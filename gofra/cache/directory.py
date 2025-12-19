from pathlib import Path

from gofra.cache.vcs import create_cache_gitignore

INCLUDED_CLEANUP_EXTENSIONS = {"", ".s", ".o"}
EXCLUDED_CLEANUP_FILENAMES = {".gitignore"}


def prepare_build_cache_directory(path: Path) -> None:
    """Try to create and fill cache directory with required files."""
    cleanup_build_cache_directory(path)
    if path.exists():
        return

    path.mkdir(exist_ok=False)
    create_cache_gitignore(path)


def cleanup_build_cache_directory(path: Path) -> None:
    """Remove all files in cache directory that is related to Gofra.

    (related unless user places any same files in cache directory).
    """
    # TODO(@kirillzhosul): Cleanup of cache directory is not implemented yet.
    for file in path.iterdir():
        if not _is_cache_file_removable(path, file):
            return
        file.unlink(missing_ok=True)


def _is_cache_file_removable(cache_path: Path, path: Path) -> bool:
    """Check is given file related to cache directory and can be safely removed in any way."""
    return (
        path.absolute().is_relative_to(cache_path.absolute())  # Must be children
        and path.suffix in INCLUDED_CLEANUP_EXTENSIONS
        and path.name not in EXCLUDED_CLEANUP_FILENAMES
    )
