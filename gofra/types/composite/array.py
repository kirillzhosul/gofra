from gofra.types._base import CompositeType, Type


class ArrayType(CompositeType):
    """Contiguous blob of memory that contains specified type in each section of size of that element."""

    _element_type: Type
    _elements_count: int

    size_in_bytes: int

    def __init__(self, element_type: Type, elements_count: int) -> None:
        assert elements_count >= 0
        self._element_type = element_type
        self.elements_count = elements_count

    def get_index_offset(self, index: int) -> int:
        """Calculate offset from start of an array to element with given index."""
        return self.element_type.size_in_bytes * index

    def is_index_oob(self, index: int) -> int:
        return index >= self.elements_count

    def __repr__(self) -> str:
        return f"{self.element_type}[{self.elements_count}]"

    @property
    def elements_count(self) -> int:
        return self._elements_count

    @property
    def element_type(self) -> Type:
        return self._element_type

    @elements_count.setter
    def elements_count(self, value: int) -> None:
        self._elements_count = value
        self.size_in_bytes = self.element_type.size_in_bytes * self.elements_count
