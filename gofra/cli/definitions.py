from gofra.codegen.targets import TARGET_T


def construct_propagated_toolchain_definitions(
    *,
    build_target_triplet: TARGET_T,
) -> dict[str, str]:
    toolchain_definitions = {}
    match build_target_triplet:
        case "aarch64-darwin":
            toolchain_definitions = {
                "OS_POSIX": "1",
                "OS_DARWIN": "1",
                "OS_MACOS": "1",
            }

        case "x86_64-linux":
            toolchain_definitions = {
                "OS_POSIX": "1",
                "OS_LINUX": "1",
            }

    return toolchain_definitions | {
        "__GOFRA_BUILD_TARGET_TRIPLET__": f'"{build_target_triplet}"',
    }
