from libgofra.assembler.drivers._get_assembler_driver import get_assembler_driver
from libgofra.targets.target import Target


def test_get_assembler_driver() -> None:
    driver = get_assembler_driver(Target.from_triplet("amd64-unknown-linux"))
    assert driver
    assert driver.name == "clang"

    driver = get_assembler_driver(Target.from_triplet("amd64-unknown-windows"))
    assert driver
    assert driver.name == "clang"

    driver = get_assembler_driver(Target.from_triplet("arm64-apple-darwin"))
    assert driver
    assert driver.name == "clang"


def test_get_assembler_driver_unknown() -> None:
    base_target = Target.from_triplet("amd64-unknown-linux")
    base_target.architecture = "x86"  # pyright: ignore[reportAttributeAccessIssue]
    driver = get_assembler_driver(base_target)
    assert driver is None
