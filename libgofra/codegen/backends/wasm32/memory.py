from collections.abc import Mapping

from libgofra.types.composite.string import StringType
from libgofra.types.composite.structure import StructureType


def wasm_pack_integer_to_memory(value: int, size: int = 8) -> str:
    """Transform integer to bytes data for WASM (WAT) memory data."""
    data = value.to_bytes(size, byteorder="little", signed=True)
    return "".join(f"\\{byte:02X}" for byte in data)


def wasm_pack_struct_to_memory(struct: StructureType, values: Mapping[str, int]) -> str:
    wasm_bytes = ""
    prev_taken_bytes = 0

    for field_name in struct.order:
        field_t = struct.get_field_type(field_name)

        padding = struct.get_field_offset(field_name) - prev_taken_bytes
        if padding:
            wasm_bytes += wasm_pack_integer_to_memory(0, size=padding)

        value = values[field_name]
        wasm_bytes += wasm_pack_integer_to_memory(value, size=field_t.size_in_bytes)

        prev_taken_bytes += field_t.size_in_bytes + padding
    return wasm_bytes


def wasm_pack_string_view_to_memory(data_ptr: int, length: int) -> str:
    return wasm_pack_struct_to_memory(
        StringType(),
        values={"data": data_ptr, "len": length},
    )
