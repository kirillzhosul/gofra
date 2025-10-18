from platform import system

from gofra.targets.target import Target


def infer_host_target() -> Target | None:
    """Try to infer target from current system."""
    match system():
        case "Darwin":
            return Target.from_triplet("arm64-apple-darwin")
        case "Linux":
            return Target.from_triplet("amd64-unknown-linux")
        case "Windows":
            return Target.from_triplet("amd64-unknown-windows")
        case _:
            return None
