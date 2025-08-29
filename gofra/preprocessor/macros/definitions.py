from pathlib import Path

from gofra.lexer.tokens import Token, TokenLocation, TokenType
from gofra.preprocessor._state import PreprocessorState
from gofra.preprocessor.macros.container import Macro


def propagate_raw_definitions(
    state: PreprocessorState,
    definitions: dict[str, str],
) -> None:
    for name, raw_definition in definitions.items():
        assert raw_definition == "1"
        token = Token(
            type=TokenType.INTEGER,
            text="1",
            value=1,
            location=TokenLocation(
                filepath=Path("/dev/null"),
                line_number=0,
                col_number=0,
            ),
        )
        state.macros[name] = Macro(
            token=token,
            name=name,
            tokens=[
                token,
            ],
        )
