from libgofra.targets import Target


def construct_propagated_toolchain_definitions(
    *,
    target: Target,
) -> dict[str, str]:
    definitions = {
        f"ARCH_{target.architecture.upper()}": "1",
        f"OS_{target.operating_system.upper()}": "1",
        f"IS_{target.endianness.upper()}_ENDIAN": "1",
    }

    if target.operating_system == "None" and target.architecture == "WASM32":
        definitions["__WASM"] = "1"

    return definitions
