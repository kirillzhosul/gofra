"""DWARF DIE opcodes."""

from enum import IntEnum


class DWARFTag(IntEnum):
    """DWARF DIE tags."""

    # fmt: off
    DW_TAG_array_type       = 1   # Array types                     (TODO)
    DW_TAG_formal_parameter = 5   # Function parameters             (TODO)
    DW_TAG_structure_member = 13  # Structure member types          (TODO)
    DW_TAG_pointer_type     = 15  # Pointer types                   (TODO)
    DW_TAG_compile_unit     = 17  # Parent root (Compilation Unit)
    DW_TAG_structure_type   = 19  # Structure types                 (TODO)
    DW_TAG_base_type        = 36  # Primitive types                 (TODO)
    DW_TAG_subprogram       = 46  # Functions
    DW_TAG_variable         = 52  # Variables                       (TODO)
    # fmt: on


class DWARFAttribute(IntEnum):
    """DWARF DIE attributes."""

    # fmt: off
    DW_AT_location              = 2  #Location (variables)           (TODO)
    DW_AT_name                  = 3  # Name string
    DW_AT_byte_size             = 11 # Size in bytes
    DW_AT_statement_list        = 16 # Line numbers
    DW_AT_low_pc                = 17 # Lowest program counter
    DW_AT_high_pc               = 18 # Highest program counter
    DW_AT_language              = 19 # Programming language code
    DW_AT_visibility            = 23 # Private / public / protected  (TODO)
    DW_AT_compilation_directory = 27 # Compilation directory
    DW_AT_const_value           = 28 # Constant value                (TODO)
    DW_AT_producer              = 37 # Producer (compiler)         
    DW_AT_declaration_file       = 58 # Index of file where defined
    DW_AT_declaration_line      = 59 # Line where defined
    DW_AT_external              = 63 # Is it visible externally
    DW_AT_type                  = 73


class DWARFForm(IntEnum):
    """DWARF DIE attribute forms."""

    # fmt: off
    DW_FORM_addr   = 1  # Address
    DW_FORM_data2  = 5  # 2 byte constant
    DW_FORM_data4  = 6  # 4 byte constant
    DW_FORM_block1 = 10 # Block with with 1 byte length
    DW_FORM_data1  = 11 # 1 byte constant 
    DW_FORM_flag    = 12  # Boolean flag
    DW_FORM_strp   = 14 # Offset inside string pool
    # fmt: on


# DWARF DIE language form attribute codes
DW_LANGUAGE_GOFRA = 36767
