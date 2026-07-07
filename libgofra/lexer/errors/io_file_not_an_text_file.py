from pathlib import Path

from libgofra.exceptions import GofraError


class IOFileNotAnTextFileError(GofraError):
    def __init__(self, path: Path) -> None:
        self.path = path

    def __repr__(self) -> str:
        return f"""File is not an text file (contains non UTF-8 text)

Tried to open file at path: `{self.path}`
(Resolves to: `{self.path.resolve()})

{self.generic_error_name}"""
