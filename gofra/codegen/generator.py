from pathlib import Path

from gofra.hir.module import Module
from gofra.targets import Target

from .get_backend import get_backend_for_target


def generate_code_for_assembler(
    output_path: Path,
    module: Module,
    target: Target,
) -> None:
    """Generate assembly from given program context and specified ARCHxOS pair into given file."""
    backend_cls = get_backend_for_target(target)

    output_path.parent.mkdir(exist_ok=True)
    with output_path.open(
        mode="w",
        errors="strict",
        buffering=1,
        newline="",
        encoding="UTF-8",
    ) as fd:
        backend = backend_cls(fd=fd, target=target, module=module)
        return backend.emit()
