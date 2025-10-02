from collections.abc import Iterable

from gofra.exceptions import GofraError


class NoToolkitForAssemblingError(GofraError):
    toolkit_required: Iterable[str]

    def __init__(self, *args: object, toolkit_required: Iterable[str]) -> None:
        super().__init__(*args)
        self.toolkit_required = toolkit_required

    def __repr__(self) -> str:
        return f"Unable to assemble program due to not all toolkit installed, required (missing ones): {','.join(self.toolkit_required)}"


class UnsupportedBuilderOperatingSystemError(GofraError):
    def __repr__(self) -> str:
        return "You are on unsupported operating system to compile that target"
