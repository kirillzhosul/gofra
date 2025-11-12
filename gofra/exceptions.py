import re
from abc import abstractmethod


def camel_to_kebab(s: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "-", s).lower()


class GofraError(Exception):
    """Parent for all Gofra errors (exceptions)."""

    @abstractmethod
    def __repr__(self) -> str:
        return f"Some internal error occurred ({super().__repr__()}), that is currently not documented"

    @property
    def generic_error_name(self) -> str:
        return f"[{camel_to_kebab(self.__class__.__name__)}]"
