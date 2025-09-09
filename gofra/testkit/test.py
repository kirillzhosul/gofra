from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path
    from subprocess import CalledProcessError, TimeoutExpired

    from gofra.codegen.targets import TARGET_T
    from gofra.exceptions import GofraError


class TestStatus(Enum):
    SKIPPED = auto()

    TOOLCHAIN_ERROR = auto()
    EXECUTION_ERROR = auto()

    SUCCESS = auto()


type ERROR = GofraError | CalledProcessError | TimeoutExpired


@dataclass(frozen=False)
class Test:
    target: TARGET_T

    path: Path
    status: TestStatus

    error: ERROR | None = None

    artifact_path: Path | None = None
