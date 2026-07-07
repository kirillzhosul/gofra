from pathlib import Path

from libgofra.exceptions import GofraError


class IOFileDoesNotExistsError(GofraError):
    def __init__(self, path: Path) -> None:
        self.path = path

    def __repr__(self) -> str:
        return f"""File not found (I/O error)

Tried to open file at path: `{self.path}`
(Resolves to: `{self.path.resolve()})

Please ensure that requested file/symlink exists!

{self.generic_error_name}"""
