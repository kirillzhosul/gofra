from gofra.targets import Target


def construct_propagated_toolchain_definitions(
    *,
    target: Target,
) -> dict[str, str]:
    toolchain_definitions = {}
    match target.operating_system:
        case "Darwin":
            toolchain_definitions = {
                "OS_POSIX": "1",
                "OS_DARWIN": "1",
                "OS_MACOS": "1",
            }

        case "Linux":
            toolchain_definitions = {
                "OS_POSIX": "1",
                "OS_LINUX": "1",
            }

    return toolchain_definitions
