import contextlib
import readline
import warnings
from collections.abc import Callable
from pathlib import Path

READLINE_DEFAULT_HISTORY_LENGTH = 1000


def finalize_readline(history_filepath: Path) -> None:
    with contextlib.suppress(FileNotFoundError):
        readline.write_history_file(history_filepath)


def try_setup_readline(history_filepath: Path) -> None:
    history_filepath.touch(exist_ok=True)
    try:
        # Enable history file
        with contextlib.suppress(FileNotFoundError):
            readline.read_history_file(history_filepath)

        readline.set_auto_history(True)
        readline.set_history_length(READLINE_DEFAULT_HISTORY_LENGTH)

        readline.parse_and_bind(r'"\e[A": previous-history')
        readline.parse_and_bind(r'"\e[B": next-history')
        readline.parse_and_bind(r'"\e[C": forward-char')
        readline.parse_and_bind(r'"\e[D": backward-char')
    except ImportError:
        warnings.warn(
            "readline not available on this system, unable to use it!",
            stacklevel=1,
        )


def read_multiline_input(
    prompt_initial: str,
    prompt_multiline: str,
    raise_eof_on: Callable[[str, int], bool],
    stop_and_preserve_on: Callable[[str, int], bool],
) -> list[str]:
    lines: list[str] = []

    while True:
        line_no = len(lines)
        prompt = prompt_multiline if line_no else prompt_initial
        try:
            line = input(prompt).strip()
        except KeyboardInterrupt:
            # Newline and omit after Ctrl+C
            print()
            continue

        if raise_eof_on(line, line_no):
            raise EOFError

        if stop_and_preserve_on(line, line_no):
            lines.append(line)
            break

        if line:
            lines.append(line)
        elif line_no > 0:
            break

    return lines
