# Architectures that is supported by Apple Linker
# may be different on some machines with MacOS
from collections.abc import Mapping
from typing import Literal

from libgofra.targets.target import Target

type APPLE_LINKER_ARCHITECTURES = Literal[
    "armv6",
    "armv7",
    "armv7s",
    "arm64",
    "arm64e",
    "arm64_32",
    "i386",
    "x86_64",
    "x86_64h",
    "armv6m",
    "armv7k",
    "armv7m",
    "armv7em",
    "armv8m.main",
    "armv8.1m.main",
]


# Mapping for `apple_linker_architecture_from_target`
APPLE_LINKER_TARGET_ARCHITECTURE_MAPPING: Mapping[
    Literal["ARM64", "AMD64"],
    Literal["arm64", "x86_64"],
] = {
    "ARM64": "arm64",
    "AMD64": "x86_64",
}


def apple_linker_architecture_from_target(target: Target) -> APPLE_LINKER_ARCHITECTURES:
    assert target.architecture in APPLE_LINKER_TARGET_ARCHITECTURE_MAPPING, (
        "Unknown target architecture for Apple linker. This is an bug in Gofra toolchain!"
    )
    return APPLE_LINKER_TARGET_ARCHITECTURE_MAPPING[target.architecture]
