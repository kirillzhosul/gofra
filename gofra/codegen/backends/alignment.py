def align_to_highest_size(size: int) -> int:
    """Shift given size so it aligns to 16 bytes (e.g 24 becomes 32).

    Modern architectures requires 16 bytes alignment, so that function will align that properly with lefting some space.
    """
    assert size >= 0, "Cannot align negative or zero numbers"
    return (size + 15) & ~15
