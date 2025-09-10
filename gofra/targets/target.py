from dataclasses import dataclass
from typing import Literal

type Triplet = Literal["amd64-unknown-linux", "arm64-apple-darwin"]


@dataclass
class Target:
    """Specifications for target build host."""

    # Conventional triplet for that target for comparsions
    triplet: Triplet

    # Based on triplet
    architecture: Literal["AMD64", "ARM64"]
    vendor: Literal["unknown", "apple"]
    operating_system: Literal["Darwin", "Linux"]

    cpu_word_size: Literal[8]
    cpu_pointer_width: Literal[8]

    file_executable_suffix: Literal[""]
    file_library_static_suffix: Literal[".a"]
    file_library_dynamic_suffix: Literal[".dylib", ".so"]
    file_assembly_suffix: Literal[".s"]
    file_object_suffix: Literal[".o"]

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
                    file_assembly_suffix=".s",
                )
