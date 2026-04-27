from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from libgofra.exceptions import GofraError

if TYPE_CHECKING:
    from pathlib import Path
    from subprocess import CalledProcessError, TimeoutExpired

    from libgofra.targets import Target


class TestStatus(Enum):
    SKIPPED = auto()

    TOOLCHAIN_ERROR = auto()
    EXPECTED_TOOLCHAIN_ERROR = auto()

    IO_MISMATCH_ERROR = auto()

    EXECUTION_STATUS_ERROR = auto()
    EXECUTION_TIMEOUT_ERROR = auto()

    SUCCESS = auto()


class GofraTestkitIOMismatchError(GofraError):
    expected_stdout: str
    actual_stdout: str

    def __init__(self, expected_stdout: str, actual_stdout: str) -> None:
        super().__init__()
        self.expected_stdout = expected_stdout
        self.actual_stdout = actual_stdout

    def __repr__(self) -> str:
        return f"IO Mismatch! Expected STDOUT: '{self.expected_stdout}', but got '{self.actual_stdout}'"


type ERROR = GofraError | CalledProcessError | TimeoutExpired


@dataclass(frozen=False)
class Test:
    target: Target

    path: Path
    status: TestStatus

    expected_exit_code: int = 0
    expected_error: str | None = None

    error: ERROR | None = None

    artifact_path: Path | None = None
