from pathlib import Path


def infer_distribution_library_paths() -> list[Path]:
    """Infers paths to library distribution.

    (as package may be installed via package managers and they may mess with files includes).
    """
    distribution_root = Path(__import__("gofra").__file__).parent
    assert distribution_root.exists(), (
        "Corrupted distribution (dist parent is non-existent, unable to infer/resolve library paths)"
    )
    return [
        # default distribution
        distribution_root / "_distlib",
        # Local package
        distribution_root.parent / "lib",
    ]
