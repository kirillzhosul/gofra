from pathlib import Path


def create_cache_gitignore(path: Path) -> None:
    """Create .gitignore file for Git VCS to not include cache into VCS."""
    with (path / ".gitignore").open("w") as f:
        f.write("# Internally created by Gofra toolchain\n")
        f.write("# Do not include this newly generated build cache into git VCS\n")
        f.write("*\n")
