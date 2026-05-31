from pathlib import Path


def create_cache_gitignore(path: Path, *, strict_must_perform: bool = False) -> None:
    """Create .gitignore file for Git VCS to not include cache into VCS."""
    gitignore = path / ".gitignore"

    content = """# Internally created by Gofra toolchain\n
# Do not include this newly generated build cache into git VCS\n
*\n"""

    try:
        gitignore.write_text(content)
    except PermissionError:
        if strict_must_perform:
            raise
