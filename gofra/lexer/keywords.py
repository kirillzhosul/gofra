from enum import Enum, auto


class Keyword(Enum):
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

    TYPECAST = auto()


class PreprocessorKeyword(Enum):
    DEFINE = auto()
    UNDEFINE = auto()

    INCLUDE = auto()

    IF_DEFINED = auto()
    END_IF = auto()


WORD_TO_PREPROCESSOR_KEYWORD = {
    "#ifdef": PreprocessorKeyword.IF_DEFINED,
    "#endif": PreprocessorKeyword.END_IF,
    "#include": PreprocessorKeyword.INCLUDE,
    "#define": PreprocessorKeyword.DEFINE,
    "#undef": PreprocessorKeyword.UNDEFINE,
}
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
    "typecast": Keyword.TYPECAST,
    **WORD_TO_PREPROCESSOR_KEYWORD,
}
KEYWORD_TO_NAME = {v: k for k, v in WORD_TO_KEYWORD.items()}
