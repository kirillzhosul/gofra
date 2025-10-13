from enum import Enum, auto


class Keyword(Enum):
    """Words that are related to language due to internal implementation like loops or parsing stage."""

    IF = auto()

    WHILE = auto()
    DO = auto()

    END = auto()

    EXTERN = auto()
    INLINE = auto()
    GLOBAL = auto()

    FUNCTION = auto()
    FUNCTION_RETURN = auto()
    FUNCTION_CALL = auto()

    STRUCT = auto()

    VARIABLE_DEFINE = auto()

    TYPE_CAST = auto()

    SYSCALL = auto()

    COPY = auto()
    DROP = auto()
    SWAP = auto()

    # Additional operations that may/or not be an part of language
    DEBUGGER_BREAKPOINT = auto()


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
WORD_TO_KEYWORD: dict[str, Keyword | PreprocessorKeyword] = {
    "if": Keyword.IF,
    "while": Keyword.WHILE,
    "do": Keyword.DO,
    "end": Keyword.END,
    "extern": Keyword.EXTERN,
    "call": Keyword.FUNCTION_CALL,
    "return": Keyword.FUNCTION_RETURN,
    "func": Keyword.FUNCTION,
    "struct": Keyword.STRUCT,
    "inline": Keyword.INLINE,
    "global": Keyword.GLOBAL,
    "var": Keyword.VARIABLE_DEFINE,
    "typecast": Keyword.TYPE_CAST,
    "breakpoint": Keyword.DEBUGGER_BREAKPOINT,
    "copy": Keyword.COPY,
    "syscall0": Keyword.SYSCALL,
    "syscall1": Keyword.SYSCALL,
    "syscall2": Keyword.SYSCALL,
    "syscall3": Keyword.SYSCALL,
    "syscall4": Keyword.SYSCALL,
    "syscall5": Keyword.SYSCALL,
    "syscall6": Keyword.SYSCALL,
    "drop": Keyword.DROP,
    "swap": Keyword.SWAP,
    **WORD_TO_PREPROCESSOR_KEYWORD,
}
KEYWORD_TO_NAME = {v: k for k, v in WORD_TO_KEYWORD.items()}
