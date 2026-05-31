from pathlib import Path

from gofra.cache.vcs import create_cache_gitignore


def test_create_cache_gitignore(tmp_path: Path) -> None:
    create_cache_gitignore(tmp_path)


def test_create_cache_gitignore_existing(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").touch()
    create_cache_gitignore(tmp_path)


def test_create_cache_gitignore_no_permissions(tmp_path: Path) -> None:
    """Test if cache creation is not failed when gitignore file has permissions not suitable for any modification."""
    (tmp_path / ".gitignore").touch(mode=0o000)
    create_cache_gitignore(tmp_path, strict_must_perform=False)
