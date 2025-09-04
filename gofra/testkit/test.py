from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from subprocess import CalledProcessError
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from gofra.codegen.targets import TARGET_T
    from gofra.exceptions import GofraError


class TestStatus(Enum):
    SKIPPED = auto()

    TOOLCHAIN_ERROR = auto()
    EXECUTION_ERROR = auto()

    SUCCESS = auto()


@dataclass(frozen=False)
class Test:
    target: TARGET_T

    path: Path
    status: TestStatus

    error: GofraError | CalledProcessError | None = None

    artifact_path: Path | None = None
