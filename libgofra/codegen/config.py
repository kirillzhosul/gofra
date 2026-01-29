from dataclasses import dataclass, field

from libgofra.linker.entry_point import LINKER_EXPECTED_ENTRY_POINT


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

    # If module specifies an entry point ref
    # define system one with this name
    system_entry_point_name: str = field(default=LINKER_EXPECTED_ENTRY_POINT)

    # If specified, and function does not require proper frame (e.g is leaf) - omit setup
    # False means even if frame pointer is unused - do setup
    omit_unused_frame_pointers: bool = field(default=False)
