from __future__ import annotations

from pathlib import Path
from platform import system
from shutil import which
from subprocess import CalledProcessError, CompletedProcess, TimeoutExpired, run
from typing import TYPE_CHECKING, Final, assert_never

from libgofra.assembler.drivers._driver_protocol import AssemblerDriverProtocol

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from libgofra.targets.target import Target


class ClangAssemblerDriver(AssemblerDriverProtocol):
    """Driver for clang assembler."""

    # This is used as default path for executable of clang
    CLANG_DEFAULT_PATH: Final[Path] = Path("/usr/bin/clang")

    # Cached result of `is_apple_clang`
    __cached_is_apple_clang: bool | None = None

    @property
    def name(self) -> str:
        return "clang"

    @classmethod
    def is_installed(cls, *, executable: Path = CLANG_DEFAULT_PATH) -> bool:
        return which(executable) is not None

    @classmethod
    def is_supported(cls, target: Target) -> bool:
        return target.architecture in ("ARM64", "AMD64")

    def assemble(
        self,
        target: Target,
        in_assembly_file: Path,
        out_object_file: Path,
        *,
        debug_information: bool,
        flags: Sequence[str],
    ) -> CompletedProcess[bytes]:
        command = self._compose_assembler_command(
            in_assembly_file=in_assembly_file,
            out_object_file=out_object_file,
            target=target,
            flags=flags,
            debug_information=debug_information,
        )

        return run(
            command,
            check=False,
            capture_output=False,
            timeout=None,
        )

    @classmethod
    def _compose_assembler_command(  # noqa: PLR0913
        cls,
        target: Target,
        in_assembly_file: Path,
        out_object_file: Path,
        *,
        debug_information: bool,
        flags: Sequence[str],
        executable: Path = CLANG_DEFAULT_PATH,
    ) -> list[str]:
        """Construct Clang command to assemble given assembly file into object file.

        :param target: Compilation target
        :param in_assembly_file: Path to assembly file as input
        :param out_object_file: Path to object file as output
        :param debug_information: If specified, will pass debug info flag to assembler and specify its version
        :param flags: Any additional flags
        :param executable: Where clang is located as executable
        """
        # fmt: off
        command = [
            str(executable),
            "-target", cls._target_flag_from_target(target),
            "-x", "assembler", # Treat input as assembly
            "-c", str(in_assembly_file), # Only assemble specified assembly file
            *flags, # Additional flags
        ]  
        # fmt: on

        if debug_information:
            # If version is specified - treat as debug -g flag also
            command.append("-g")
            command.append("-gdwarf-4")

        # Output into that file
        command.extend(("-o", str(out_object_file)))
        return command

    @classmethod
    def _target_flag_from_target(cls, target: Target) -> str:
        """Transform Gofra target into target flag suitable for Clang."""
        match target.triplet:
            case "arm64-apple-darwin" | "amd64-unknown-linux" | "amd64-unknown-windows":
                return target.triplet
            case "wasm32-unknown-none":
                raise NotImplementedError
            case _:
                assert_never(target.triplet)

    @classmethod
    def _is_apple_clang(
        cls,
        *,
        on_shell_call: Callable[[list[Path | str]], None] | None = None,
        timeout: float = 5.0,
        executable: Path = CLANG_DEFAULT_PATH,
    ) -> bool:
        """Is currently installed clang is Apple version (MacOS specific).

        On MacOS clang is slightly different, so we must check for that

        DEPRECATED: Currently, there is no check for Apple clang, but this may become handy later if we introduce that again
        TODO: Use or remove that from source

        :param on_shell_call: If required to call shell, pass called command here before execution e.g for logging
        :param timeout: If required to call shell, timeout for that command, should be not required to change
        :param executable
        """
        if cls.__cached_is_apple_clang is not None:
            return cls.__cached_is_apple_clang  # Already called and cached

        cls.__cached_is_apple_clang = cls.__cached_is_apple_clang or False

        is_darwin = system() == "Darwin"
        if not is_darwin:
            # Apple Clang is only for MacOS
            return False

        try:
            command = [executable, "--version"]
            if on_shell_call:
                on_shell_call(command)
            process = run(
                command,
                shell=False,
                check=True,
                text=False,
                capture_output=True,
                timeout=timeout,
            )
        except (TimeoutExpired, CalledProcessError):
            # It possibly may mean an error
            # but for this scenario we may want to fall before/after this function
            return False

        cls.__cached_is_apple_clang = b"apple" in process.stdout
        return cls.__cached_is_apple_clang
