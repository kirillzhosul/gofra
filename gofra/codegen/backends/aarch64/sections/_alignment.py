from gofra.types._base import Type


def get_type_data_alignment(t: Type) -> int | None:
    """Get power-of-two alignment in bytes for specified type that will be located in data sections."""
    # TODO(@kirillzhosul): Align by specifications of type not general byte size

    if t.size_in_bytes >= 16:
        return 4
    if t.size_in_bytes >= 8:
        return 3
    if t.size_in_bytes >= 4:
        return 2
    return None
