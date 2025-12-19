from dataclasses import dataclass
from typing import Literal

type Triplet = Literal[
    "amd64-unknown-linux",
    "arm64-apple-darwin",
    "amd64-unknown-windows",
]


@dataclass(eq=True)
class Target:
    """Specifications for target build host."""

    # Conventional triplet for that target for comparisons
    triplet: Triplet

    # Based on triplet
    architecture: Literal["AMD64", "ARM64"]
    vendor: Literal["unknown", "apple"]
    operating_system: Literal["Darwin", "Linux", "Windows"]

    cpu_word_size: Literal[8]
    cpu_pointer_width: Literal[8]

    endianness: Literal["little", "big"]

    file_executable_suffix: Literal["", ".exe"]
    file_library_static_suffix: Literal[".a", ".lib"]
    file_library_dynamic_suffix: Literal[".dylib", ".so", ".dll"]
    file_assembly_suffix: Literal[".s", ".asm"]
    file_object_suffix: Literal[".o", ".obj"]

    @staticmethod
    def from_triplet(triplet: Triplet) -> "Target":
        match triplet:
            case "arm64-apple-darwin":
                return Target(
                    triplet=triplet,
                    vendor="apple",
                    architecture="ARM64",
                    operating_system="Darwin",
                    cpu_pointer_width=8,
                    cpu_word_size=8,
                    file_executable_suffix="",
                    file_library_static_suffix=".a",
                    file_library_dynamic_suffix=".dylib",
                    file_object_suffix=".o",
                    file_assembly_suffix=".s",
                    endianness="little",
                )
            case "amd64-unknown-windows":
                return Target(
                    triplet=triplet,
                    vendor="unknown",
                    architecture="AMD64",
                    operating_system="Windows",
                    cpu_pointer_width=8,
                    cpu_word_size=8,
                    file_executable_suffix=".exe",
                    file_library_static_suffix=".lib",
                    file_library_dynamic_suffix=".dll",
                    file_object_suffix=".obj",
                    file_assembly_suffix=".asm",
                    endianness="little",
                )
            case "amd64-unknown-linux":
                return Target(
                    triplet=triplet,
                    vendor="unknown",
                    architecture="AMD64",
                    operating_system="Linux",
                    cpu_pointer_width=8,
                    cpu_word_size=8,
                    file_executable_suffix="",
                    file_library_static_suffix=".a",
                    file_library_dynamic_suffix=".so",
                    file_object_suffix=".o",
                    endianness="little",
                    file_assembly_suffix=".s",
                )
