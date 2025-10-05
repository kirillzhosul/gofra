# See `compose_apple_linker_command` `platform_version`
from typing import Literal

type APPLE_LINKER_PLATFORMS = Literal[
    "macos",
    "ios",
    "tvos",
    "watchos",
    "bridgeos",
    "visionos",
    "xros",
    "mac-catalyst",
    "ios-simulator",
    "tvos-simulator",
    "watchos-simulator",
    "visionos-simulator",
    "xros-simulator",
    "driverkit",
    "firmware",
    "sepOS",
]
