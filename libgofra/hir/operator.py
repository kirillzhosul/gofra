from dataclasses import dataclass
from enum import Enum, auto

from libgofra.lexer.tokens import Token, TokenLocation
from libgofra.types._base import Type
from libgofra.types.composite.structure import StructureType


class OperatorType(Enum):
    """HIR type of an operator.

    HIR operator types is flat and contains all possible operations / instructions.
    """

    # Push arbitrary number (integer of arbitrary byte size) onto stack
    # it is up to the next layers (e.g codegen) to infer that size with corresponding storage
    # any type which is scalar/arithmetical is treated as an integer (e.g bool)
    # TODO(@kirillzhosul): Proper inference of integer size
    PUSH_INTEGER = auto()
    PUSH_FLOAT = auto()

    # Push address of static string onto stack (structure type definition)
    # TODO(@kirillzhosul): Review C-Strings - https://github.com/kirillzhosul/gofra/issues/27
    PUSH_STRING = auto()

    # Push address of variable (local or global one, storage class is not specified)
    PUSH_VARIABLE_ADDRESS = auto()

    # Read value from variable and push on stack
    # (alternative to PUSH_VARIABLE_ADDRESS -> MEMORY_VARIABLE_READ)
    PUSH_VARIABLE_VALUE = auto()

    # Internal operation when function has parameters
    # Specifies that parameter local variable must be loaded right now
    # (moved from stack, registers) into local argument variable location
    LOAD_PARAM_ARGUMENT = auto()

    # Shift current pointer to an struct for given structure field
    STRUCT_FIELD_OFFSET = auto()

    # Return from current function execution to the caller
    FUNCTION_RETURN = auto()

    # Call specified function
    FUNCTION_CALL = auto()

    # Typechecker mark to treat current (type) stack value as specified type
    STATIC_TYPE_CAST = auto()

    # Conditional blocks
    # Transformed at LIR into proper JUMP_IF_ZERO instructions
    # TODO(@kirillzhosul): Probably, requires proper refactoring with conditional blocks
    CONDITIONAL_IF = auto()
    CONDITIONAL_DO = auto()
    CONDITIONAL_WHILE = auto()
    CONDITIONAL_FOR = auto()

    CONDITIONAL_END = auto()

    # System calls for architectures and operating system which supports them
    # Has number of the arguments as operand
    SYSCALL = auto()

    # On-stack operations
    # TODO(@kirillzhosul): Proper inference of operand size (e.g stack with [A:8B, A:8B, B:8BIT] is meant to deal with A, B or only most significant bytes?)
    STACK_COPY = auto()
    STACK_DROP = auto()
    STACK_SWAP = auto()

    # On-stack arithmetic operations
    ARITHMETIC_PLUS = auto()
    ARITHMETIC_MINUS = auto()
    ARITHMETIC_MULTIPLY = auto()
    ARITHMETIC_DIVIDE = auto()
    ARITHMETIC_MODULUS = auto()

    # On-stack comparison operations
    COMPARE_EQUALS = auto()
    COMPARE_NOT_EQUALS = auto()
    COMPARE_LESS = auto()
    COMPARE_GREATER = auto()
    COMPARE_LESS_EQUALS = auto()
    COMPARE_GREATER_EQUALS = auto()

    # On-stack Logical operations
    LOGICAL_OR = auto()
    LOGICAL_AND = auto()

    # On-stack bitwise operations
    BITWISE_OR = auto()
    BITWISE_AND = auto()
    BITWISE_XOR = auto()

    # On-stack bit shift operations.
    # Shift semantic: arithmetic / logical type is not clarified
    SHIFT_RIGHT = auto()
    SHIFT_LEFT = auto()

    # On-stack IO for variables memory (read/write)
    # Up to the next layer to decide size of the instruction (e.g read 8/16/32 bytes) from variable
    MEMORY_VARIABLE_READ = auto()
    MEMORY_VARIABLE_WRITE = auto()

    # Additional operations that may/or not be an part of language
    DEBUGGER_BREAKPOINT = auto()


type StructAccessor = tuple[StructureType, str]  # TODO (@kirillzhosul): must refactor


@dataclass(frozen=False, slots=True)
class Operator:
    type: OperatorType
    token: Token
    operand: int | float | str | Type | StructAccessor | None

    jumps_to_operator_idx: int | None = None

    @property
    def location(self) -> TokenLocation:
        """Location of an token which corresponds to that operator."""
        return self.token.location
