from platform import system

from gofra.targets.target import Target


def infer_host_target() -> Target | None:
    """Try to infer target from current system."""
    assert system() in ["Darwin", "Linux"]

    match system():
        case "Darwin":
            return Target.from_triplet("arm64-apple-darwin")
        case "Linux":
            return Target.from_triplet("amd64-unknown-linux")
        case _:
            return None
