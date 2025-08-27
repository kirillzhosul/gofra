from enum import IntEnum, auto


class Keyword(IntEnum):
    """Words that are related to language due to internal implementation like loops or parsing stage."""

    IF = auto()

    WHILE = auto()
    DO = auto()

    END = auto()

    MEMORY = auto()

    EXTERN = auto()
    INLINE = auto()
    GLOBAL = auto()

    FUNCTION = auto()
    FUNCTION_RETURN = auto()
    FUNCTION_CALL = auto()

    # Preprocessor
    PP_IFDEF = auto()
    PP_ENDIF = auto()
    PP_INCLUDE = auto()
    PP_MACRO = auto()


WORD_TO_KEYWORD = {
    "if": Keyword.IF,
    "while": Keyword.WHILE,
    "do": Keyword.DO,
    "end": Keyword.END,
    "extern": Keyword.EXTERN,
    "call": Keyword.FUNCTION_CALL,
    "return": Keyword.FUNCTION_RETURN,
    "func": Keyword.FUNCTION,
    "inline": Keyword.INLINE,
    "memory": Keyword.MEMORY,
    "global": Keyword.GLOBAL,
    # Preprocessor
    "#ifdef": Keyword.PP_IFDEF,
    "#endif": Keyword.PP_ENDIF,
    "#include": Keyword.PP_INCLUDE,
    "#macro": Keyword.PP_MACRO,
}
KEYWORD_TO_NAME = {v: k for k, v in WORD_TO_KEYWORD.items()}
