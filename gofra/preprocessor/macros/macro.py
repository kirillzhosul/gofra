from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from gofra.lexer import Token

if TYPE_CHECKING:
    from collections.abc import MutableSequence

    from gofra.lexer.tokens import TokenLocation


@dataclass(frozen=True)
class Macro:
    """Preprocessor macro definition for text substition and conditional compilation.

    Macros are named containers of sequence of tokens (e.g raw text) to be expanded
    when the macro name invocation is encoutered during preprocessing.

    They also used and desired to be used in preprocessor conditional blocks
    (e.g `#if`, `#ifdef` for conditional compilation)

    Language workflow:
        Preprocessor encouter macro definition like:
        `#define VALUE 1024`

        It consumes that whole block until `EOL` (end-of-line) token (macro definitions are line-dependant)
        Next time when preprocessor encouter an name of that token in tokens, e.g:
        `{code} VALUE {code}`
        It will consume that invocation and expand that tokens which that macro containts, e.g:
        `{code} 1024 {code}`

        That stage is related to preprocessor so all definition directives will be eliminated before parser stage.

    Command-Line-Interface (CLI) definitions:
        Definitions (macros) may be propageted from the CLI via `-D` flag, e.g: `-DMACRO_NAME` or `-DMACRO_NAME=128`
        They will be treated as same as file-contained definitions would be.

    Read more:
        Text substition macros: https://en.wikipedia.org/wiki/Macro_(computer_science)#Text-substitution_macros
    """

    # Where is that definitions begins (an reference to `#define` token)
    # There is possibility that definition is comes from CLI or toolchain
    location: TokenLocation

    # Definition block name
    # stored here as possible future reference, mostly should be unused
    name: str

    # Actual macro container, contains tokens which that macro would expand into
    tokens: MutableSequence[Token] = field(default_factory=deque[Token])
