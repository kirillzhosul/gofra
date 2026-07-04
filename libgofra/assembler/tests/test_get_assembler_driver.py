from pathlib import Path
from subprocess import CompletedProcess
from typing import Any

from pytest import MonkeyPatch

from libgofra.assembler.drivers._get_assembler_driver import get_assembler_driver
from libgofra.targets.target import Target


def test_get_assembler_driver() -> None:
    driver = get_assembler_driver(
        Target.from_triplet("amd64-unknown-linux"),
        installed_only=False,
    )
    assert driver
    assert driver.name == "clang"

    driver = get_assembler_driver(
        Target.from_triplet("amd64-unknown-windows"),
        installed_only=False,
    )
    assert driver
    assert driver.name == "clang"

    driver = get_assembler_driver(
        Target.from_triplet("arm64-apple-darwin"),
        installed_only=False,
    )
    assert driver
    assert driver.name == "clang"

    driver = get_assembler_driver(
        Target.from_triplet("wasm32-unknown-none"),
        installed_only=False,
    )
    assert driver
    assert driver.name == "wabt{wat2wasm}"


def test_get_assembler_driver_unknown() -> None:
    base_target = Target.from_triplet("amd64-unknown-linux")
    base_target.architecture = "x86"  # pyright: ignore[reportAttributeAccessIssue]
    driver = get_assembler_driver(base_target, installed_only=False)
    assert driver is None


def test_mocked_subprocess_run(monkeypatch: "MonkeyPatch") -> None:
    calls: list[tuple[tuple[list[str], ...], dict[str, object]]] = []

    def mock_run(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        calls.append((args, kwargs))
        return CompletedProcess(args=args, returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(
        "libgofra.assembler.drivers.clang.run",
        mock_run,
        raising=False,
    )
    driver = get_assembler_driver(
        Target.from_triplet("amd64-unknown-linux"),
        installed_only=False,
    )
    assert driver
    assert driver.name == "clang"

    driver.assemble(
        target=Target.from_triplet("amd64-unknown-linux"),
        in_assembly_file=Path("test.s"),
        out_object_file=Path("test.o"),
        debug_information=False,
        flags=[],
    )

    assert len(calls) == 1
    proc_cmd = " ".join(calls[0][0][0])
    assert proc_cmd.endswith(
        "clang -target amd64-unknown-linux -x assembler -c test.s -o test.o",
    )
