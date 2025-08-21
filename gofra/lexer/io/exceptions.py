from pathlib import Path

from gofra.exceptions import GofraError


class IOFileDoesNotExistsError(GofraError):
    def __init__(self, *args: object, path: Path) -> None:
        super().__init__(*args)
        self.path = path

    def __repr__(self) -> str:
        return f"""File not found (I/O error)

Tried to open file at path: `{self.path}`
(Resolves to: `{self.path.resolve()})

Please ensure that requested file/symlink exists!"""


class IOFileNotAnFileError(GofraError):
    def __init__(self, *args: object, path: Path) -> None:
        super().__init__(*args)
        self.path = path

    def __repr__(self) -> str:
        return f"""File is not an file 
(Is an directory?: {"Yes" if self.path.is_dir() else "No"})

Tried to open file at path: `{self.path}`
(Resolves to: `{self.path.resolve()})

Please ensure that requested file is an file and not an directory or anything else!"""
