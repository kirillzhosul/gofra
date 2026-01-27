from dataclasses import dataclass, field


@dataclass
class CodegenConfig:
    """Configuration for codegen.

    Low-level configuration specifies how to generate code by codegen
    (Do not mismatch with something like general parameters, they are forced by compiler)
    """

    # Disables emitting of any comments from compiler
    no_compiler_comments: bool = field(default=False)

    # Enables emitting CFI (Call Frame Information)
    # Suitable for x86, ARM architectures
    # allows unwinding, additional debug information
    dwarf_emit_cfi: bool = field(default=False)

    # Align functions with that amount bytes
    # <= 1 means no alignment
    # None: use target default
    align_functions_bytes: int | None = field(default=None)
