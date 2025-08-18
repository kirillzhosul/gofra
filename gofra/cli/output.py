from sys import stderr, stdout
from typing import Literal

type MessageLevel = Literal["INFO", "ERROR", "WARNING", "SUCCESS"]


class CLIColor:
    RED = "\033[91m"
    GREEN = "\033[92m"
    RESET = "\033[0m"
    YELLOW = "\033[93m"


def cli_message(level: MessageLevel, text: str, *, verbose: bool = True) -> None:
    """Emit an message to CLI user with given level, applying FD according to level."""
    fd = stdout if level not in ("ERROR",) else stderr

    if level == "INFO" and not verbose:
        return

    color_mapping: dict[MessageLevel, str] = {
        "ERROR": CLIColor.RED,
        "WARNING": CLIColor.YELLOW,
        "SUCCESS": CLIColor.GREEN,
    }
    print(
        f"{color_mapping.get(level, CLIColor.RESET)}[{level}] {text}{CLIColor.RESET}",
        file=fd,
    )
