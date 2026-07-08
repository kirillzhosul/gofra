from collections.abc import Iterable
from pathlib import Path


def try_resolve_and_find_real_include_path(
    path: Path,
    current_path: Path,
    search_paths: Iterable[Path],
) -> Path | None:
    """Resolve real import path and try to search for possible location of include (include directories system)."""
    traversed_paths = (
        # 1. Try path where callee request an include
        current_path.parent,
        # 2. Try CLI toolchain call directory
        Path("./"),
        # 3. Traverse each search path
        *search_paths,
    )
    for search_path in traversed_paths:
        probable_path = search_path.joinpath(path)
        if not probable_path.exists(follow_symlinks=True):
            probable_path = search_path.joinpath(path).with_suffix(".gof")
            if not probable_path.exists(follow_symlinks=True):
                continue

        if probable_path.is_file():
            # We found an straightforward file reference
            return probable_path

        # Non-existent file here or directory reference.
        if not probable_path.is_dir():
            continue

        probable_package = Path(probable_path / probable_path.name).with_suffix(
            ".gof",
        )
        if probable_package.exists():
            return probable_package
    return None
