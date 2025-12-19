from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path
    from subprocess import CalledProcessError, TimeoutExpired

    from libgofra.exceptions import GofraError
    from libgofra.targets import Target


class TestStatus(Enum):
    SKIPPED = auto()

    TOOLCHAIN_ERROR = auto()

    EXECUTION_STATUS_ERROR = auto()
    EXECUTION_TIMEOUT_ERROR = auto()

    SUCCESS = auto()


type ERROR = GofraError | CalledProcessError | TimeoutExpired


@dataclass(frozen=False)
class Test:
    target: Target

    path: Path
    status: TestStatus

    expected_exit_code: int = 0

    error: ERROR | None = None

    artifact_path: Path | None = None
