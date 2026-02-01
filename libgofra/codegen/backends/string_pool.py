from collections.abc import ItemsView, MutableMapping


class StringPool:
    """General string pool for codegen.

    Provides general support for deduplication and handling tracking labeling for unique strings.
    """

    # TODO: CSO (common substring optimization)
    # TODO: Wasm does not uses it as spills strings

    content_to_label: MutableMapping[str, str]

    def __init__(self) -> None:
        self.content_to_label = {}

    def add(self, raw_string: str) -> str:
        """Track given raw string into pool, returning label that must be used for it."""
        if raw_string in self.content_to_label:
            return self.content_to_label[raw_string]

        string_key = ".str%d" % len(self.content_to_label)
        self.content_to_label[raw_string] = string_key

        return string_key

    def is_empty(self) -> bool:
        return not bool(self.content_to_label)

    def get_view(self) -> ItemsView[str, str]:
        """Iterate over pool to emit static data section."""
        return self.content_to_label.items()
