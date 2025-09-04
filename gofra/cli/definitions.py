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
                "ARCH_AARCH64": "1",
            }

        case "x86_64-linux":
            toolchain_definitions = {
                "OS_POSIX": "1",
                "OS_LINUX": "1",
                "ARCH_X86_64": "1",
            }

    return toolchain_definitions
