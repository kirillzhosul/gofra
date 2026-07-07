from pathlib import Path

from libgofra.exceptions import GofraError


class IOFileNotAnFileError(GofraError):
    def __init__(self, path: Path) -> None:
        self.path = path

    def __repr__(self) -> str:
        return f"""File is not an file 
(Is an directory?: {"Yes" if self.path.is_dir() else "No"})

Tried to open file at path: `{self.path}`
(Resolves to: `{self.path.resolve()})

Please ensure that requested file is an file and not an directory or anything else!

{self.generic_error_name}"""
