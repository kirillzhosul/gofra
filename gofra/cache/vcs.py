import contextlib
from pathlib import Path


def try_create_cache_gitignore(path: Path) -> None:
    """Create .gitignore file for Git VCS to not include cache into VCS."""
    gitignore = path / ".gitignore"

    content = """# Internally created by Gofra toolchain\n
# Do not include this newly generated build cache into git VCS\n
*\n"""

    with contextlib.suppress(PermissionError):
        gitignore.write_text(content)
