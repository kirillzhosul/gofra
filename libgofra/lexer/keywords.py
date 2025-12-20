from enum import Enum, auto


class Keyword(Enum):
    """Words that are related to language due to internal implementation like loops or parsing stage."""

    IF = auto()

    WHILE = auto()
    FOR = auto()
    DO = auto()
    IN = auto()

    END = auto()

    EXTERN = auto()
    INLINE = auto()
    GLOBAL = auto()
    NO_RETURN = auto()

    FUNCTION = auto()
    FUNCTION_RETURN = auto()
    FUNCTION_CALL = auto()

    IMPORT = auto()

    INLINE_RAW_ASM = auto()
    COMPILE_TIME_ERROR = auto()

    STRUCT = auto()

    CONST = auto()
    VARIABLE_DEFINE = auto()

    TYPE_CAST = auto()
    TYPE_DEFINE = auto()

    SIZEOF = auto()
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
    IF_NOT_DEFINED = auto()
    END_IF = auto()


WORD_TO_PREPROCESSOR_KEYWORD = {
    "#ifdef": PreprocessorKeyword.IF_DEFINED,
    "#ifndef": PreprocessorKeyword.IF_NOT_DEFINED,
    "#endif": PreprocessorKeyword.END_IF,
    "#include": PreprocessorKeyword.INCLUDE,
    "#define": PreprocessorKeyword.DEFINE,
    "#undef": PreprocessorKeyword.UNDEFINE,
}
WORD_TO_KEYWORD: dict[str, Keyword | PreprocessorKeyword] = {
    # Function definition
    "func": Keyword.FUNCTION,
    "inline": Keyword.INLINE,
    "global": Keyword.GLOBAL,
    "no_return": Keyword.NO_RETURN,
    "extern": Keyword.EXTERN,
    # Other definition
    "const": Keyword.CONST,
    "struct": Keyword.STRUCT,
    "var": Keyword.VARIABLE_DEFINE,
    "type": Keyword.TYPE_DEFINE,
    # Constructions
    "if": Keyword.IF,
    "while": Keyword.WHILE,
    "in": Keyword.IN,
    "for": Keyword.FOR,
    "do": Keyword.DO,
    "end": Keyword.END,
    # Statements / operators
    "call": Keyword.FUNCTION_CALL,
    "import": Keyword.IMPORT,
    "compile_error": Keyword.COMPILE_TIME_ERROR,
    "inline_raw_asm": Keyword.INLINE_RAW_ASM,
    "return": Keyword.FUNCTION_RETURN,
    "sizeof": Keyword.SIZEOF,
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
