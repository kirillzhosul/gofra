from gofra.exceptions import GofraError
from gofra.lexer.tokens import TokenLocation
from gofra.types._base import Type


class TypeHasNoCompileTimeInitializerParserError(GofraError):
    def __init__(
        self,
        *args: object,
        type: Type,  # noqa: A002
        for_variable_at: TokenLocation,
    ) -> None:
        super().__init__(*args)
        self.type = type
        self.for_variable_at = for_variable_at

    def __repr__(self) -> str:
        return f"""Type `{self.type}` has no initializer known at compile time (for variable at {self.for_variable_at})!

Consider using manual initializer logic

[parser-no-compile-time-known-initializer-for-var]"""
