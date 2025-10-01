from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from gofra.codegen.lir.registers import LIRImmediate, LIRVirtualRegister
from gofra.lexer.tokens import TokenLocation
from gofra.types._base import Type


class LIRBaseOp(Protocol):
    """Base operation class for LIR.

    Childrens specify additional payload within operation (e.g something like operands).
    """

    source_location: TokenLocation | None = None


@dataclass
class LIRFunctionCallPrepareArguments(LIRBaseOp):
    """Prepare for next function call by loading arguments from parameters (e.g LIRFunctionCall as next instruction). Arguments must be on stack, and ABI is implemented by target."""

    arguments: Sequence[Type]


@dataclass
class LIRFunctionAcquireArguments(LIRBaseOp):
    """Load arguments for current function via ABI as this function accepts given arguments defined in parameters."""

    arguments: Sequence[Type]


@dataclass
class LIRFunctionCallAcquireRetval(LIRBaseOp):
    """Get return value from function call (e.g LIRFunctionCall as previous instruction) and push it on stack."""

    # Must be an non-void type as LIR generator will skip those instructions
    return_type: Type


@dataclass
class LIRFunctionCall(LIRBaseOp):
    """Call an function with given name.

    Function specification may be found in functions table.
    """

    # Key in functions table to call
    function: str


@dataclass
class LIRFunctionPrepareRetval(LIRBaseOp):
    """Load return value for next return from function instruction (e.g LIRFunctionReturn)."""

    type: Type


@dataclass
class LIRFunctionReturn(LIRBaseOp):
    """Return from a function to a caller via Link-Register."""


@dataclass
class LIRUnconditionalJumpToLabel(LIRBaseOp):
    """Directly jump to label without condition check."""

    label: str


@dataclass
class LIRPushInteger32Bits(LIRBaseOp):
    """Push given integer (4 byte) onto stack."""

    value: int


@dataclass
class LIRFunctionSaveFrame(LIRBaseOp):
    """Save stack frame and LR within function prologue, allocates on-frame locals."""

    # Locals to allocate
    # Frame must store local offsets for that locals for next load via `LIRPushLocalFrameVariableAddress`
    locals: Mapping[str, Type]


@dataclass
class LIRFunctionRestoreFrame(LIRBaseOp):
    """Restore frame created by current function."""

    # Locals that was allocated on frame stack
    locals: Sequence[Type]


@dataclass
class LIRPushLocalFrameVariableAddress(LIRBaseOp):
    """Push address of an local variable on a frame to stack.

    Offsets must be calculated/stored when `LIRFunctionSaveFrame` encoutered.
    """

    name: str


@dataclass
class LIRPushStaticGlobalVariableAddress(LIRBaseOp):
    """Push address of an static global variable (e.g in BSS segment) to an stack."""

    name: str


@dataclass
class LIRPushStaticStringAddress(LIRBaseOp):
    """Push address of static string to an stack.

    Behaves almost same like `LIRPushStaticGlobalVariableAddress`
    """

    segment: str


@dataclass
class LIRLabel(LIRBaseOp):
    """Define an label for conditional and unconditional jumps."""

    label: str


@dataclass
class LIRJumpIfZero(LIRBaseOp):
    """Conditional jump to given label if current stack value is not zero. (pop and check)."""

    label: str
    register: LIRVirtualRegister


@dataclass
class LIRDropStackSlot(LIRBaseOp):
    """Drop current stack slots by shifting stack pointer."""


@dataclass
class LIRDebuggerTraceTrap(LIRBaseOp):
    """Throw an trace-trap for debugger halting an execution."""


@dataclass
class LIRPopFromStackIntoRegisters(LIRBaseOp):
    """Pop values from the stack into specified registers in the given order.

    This operation pops the top N values from the stack and moves them into
    the specified registers, where N is the number of registers provided.
    The popping order follows the stack's LIFO (Last-In-First-Out) semantics,
    while the register assignment follows the order specified in the registries list.

    Stack behavior:
    - The top of stack (most recently pushed value) goes to the first register
    - Earlier stack values go to subsequent registers

    Example:
        If stack contains (from top to bottom): [a, b, c, d]
        And operation: LIRPopFromStackIntoRegisters(registries=[x0, x1])
        Result:
          - x0 = a (top of stack)
          - x1 = b (next stack value)
        Stack after operation: [c, d]

    """

    registries: Sequence[LIRVirtualRegister]


@dataclass
class LIRPushRegistersOntoStack(LIRBaseOp):
    """Push given virtual registries onto stack."""

    registries: Sequence[LIRVirtualRegister]


@dataclass
class LIRSystemCallPrepareArguments(LIRBaseOp):
    """Prepare for next system call by loading arguments (e.g LIRSystemCall as next instruction). ABI for system calls is target-specific."""

    # Amount of arguments to load from stack.
    arguments_count: int


@dataclass
class LIRSystemCall(LIRBaseOp):
    """Perform target system call, arguments must be loaded via `LIRSystemCallPrepareArguments` and return value is always loaded."""


@dataclass
class LIRLoadMemoryAddress(LIRBaseOp):
    # Register which holds address to load
    address_register: LIRVirtualRegister

    # Register where to load that address
    result_register: LIRVirtualRegister


@dataclass
class LIRStoreIntoMemoryAddress(LIRBaseOp):
    """Store given value from virtual register into memory address."""

    # Register which holds address to store into
    address_register: LIRVirtualRegister

    # Register which holds value to store.
    value_register: LIRVirtualRegister


@dataclass
class LIRBaseRegsThreeAddrsOp(LIRBaseOp):
    result_register: LIRVirtualRegister
    operand_a: LIRVirtualRegister | LIRImmediate
    operand_b: LIRVirtualRegister | LIRImmediate


@dataclass
class LIRAddRegs(LIRBaseRegsThreeAddrsOp): ...


@dataclass
class LIRSubRegs(LIRBaseRegsThreeAddrsOp): ...


@dataclass
class LIRBitwiseAndRegs(LIRBaseRegsThreeAddrsOp): ...


@dataclass
class LIRBitwiseOrRegs(LIRBaseRegsThreeAddrsOp): ...


@dataclass
class LIRModulusRegs(LIRBaseRegsThreeAddrsOp): ...


@dataclass
class LIRMulRegs(LIRBaseRegsThreeAddrsOp): ...


@dataclass
class LIRFloorDivRegs(LIRBaseRegsThreeAddrsOp):
    """Divide two registers and store integer result (e.g without decimal remainder)."""


@dataclass
class LIRLogicalCompareRegisters(LIRBaseRegsThreeAddrsOp):
    """Compare two registers and store result as bit* (0 or 1) into register."""

    comparsion: Literal["!=", ">", ">=", "<", "<=", "=="]


@dataclass
class LIRSystemExit(LIRBaseOp):
    """Exit an program (stop exection) with 0 exit code.

    Required for systems to not get segmentation fault and proper exit.
    """
