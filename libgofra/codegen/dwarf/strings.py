from collections.abc import MutableMapping

# Who produced that
DWARF_PRODUCER_STRING = "Gofra Compiler (gofra)"


class DWARFStringPool:
    """String pool for DWARF offset calculations."""

    pool: MutableMapping[str, int]
    offset: int

    def __init__(self) -> None:
        self.pool = {}
        self.offset = 0

    def load(self, string: str) -> int:
        """Load string into string pool if not loaded, return offset within whole pool."""
        if string in self.pool:
            # Already loaded, offset known
            return self.pool[string]

        offset = self.offset
        self.pool[string] = offset

        self.offset += len(string) + 1  # Null terminated
        return offset
