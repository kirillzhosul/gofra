from collections.abc import MutableSequence
from dataclasses import dataclass

from libgofra.codegen.dwarf.opcodes import DWARFAttribute, DWARFForm, DWARFTag


@dataclass
class DWARFAbbreviation:
    tag: DWARFTag
    has_children: bool
    fields: MutableSequence[tuple[DWARFAttribute, DWARFForm]]


DWARF_COMPILE_UNIT_ABBREVIATION = DWARFAbbreviation(
    tag=DWARFTag.DW_TAG_compile_unit,
    has_children=True,
    fields=[
        (DWARFAttribute.DW_AT_producer, DWARFForm.DW_FORM_strp),
        (DWARFAttribute.DW_AT_language, DWARFForm.DW_FORM_data2),
        (DWARFAttribute.DW_AT_name, DWARFForm.DW_FORM_strp),
        (DWARFAttribute.DW_AT_statement_list, DWARFForm.DW_FORM_data4),
        (DWARFAttribute.DW_AT_compilation_directory, DWARFForm.DW_FORM_strp),
        (DWARFAttribute.DW_AT_low_pc, DWARFForm.DW_FORM_addr),
        (DWARFAttribute.DW_AT_high_pc, DWARFForm.DW_FORM_addr),
    ],
)

DWARF_SUBPROGRAM_ABBREVIATION = DWARFAbbreviation(
    tag=DWARFTag.DW_TAG_subprogram,
    has_children=True,
    fields=[
        (DWARFAttribute.DW_AT_low_pc, DWARFForm.DW_FORM_addr),
        (DWARFAttribute.DW_AT_high_pc, DWARFForm.DW_FORM_addr),
        (DWARFAttribute.DW_AT_name, DWARFForm.DW_FORM_strp),
        (DWARFAttribute.DW_AT_declaration_file, DWARFForm.DW_FORM_data1),
        (DWARFAttribute.DW_AT_declaration_line, DWARFForm.DW_FORM_data1),
        (DWARFAttribute.DW_AT_external, DWARFForm.DW_FORM_flag),
    ],
)
