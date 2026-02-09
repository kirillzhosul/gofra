"""DWARF debug information generator."""

from collections.abc import MutableMapping, MutableSequence
from pathlib import Path

from libgofra.codegen.backends.aarch64.writer import WriterProtocol
from libgofra.codegen.dwarf.abbreviations import (
    DWARF_BASE_TYPE_ABBREVIATION,
    DWARF_COMPILE_UNIT_ABBREVIATION,
    DWARF_SUBPROGRAM_ABBREVIATION,
    DWARF_VARIABLE_ABBREVIATION,
)
from libgofra.codegen.dwarf.labels import (
    DW_LABEL_ABBREV,
    DW_LABEL_FUNC_BEGIN_FMT,
    DW_LABEL_FUNC_END_FMT,
    DW_LABEL_INFO,
    DW_LABEL_INFO_BEGIN,
    DW_LABEL_INFO_END,
)
from libgofra.codegen.dwarf.opcodes import (
    DW_LANGUAGE_GOFRA,
    DWARFAttribute,
    DWARFEncoding,
    DWARFForm,
)
from libgofra.codegen.dwarf.strings import DWARF_PRODUCER_STRING, DWARFStringPool
from libgofra.codegen.dwarf.writer import DWARFFieldWriter
from libgofra.codegen.sections._factory import SectionType
from libgofra.hir.function import Function
from libgofra.hir.module import Module
from libgofra.lexer.tokens import TokenLocation
from libgofra.types._base import PrimitiveType
from libgofra.types.primitive.boolean import BoolType
from libgofra.types.primitive.character import CharType
from libgofra.types.primitive.void import VoidType

# This is DWARF version 4 (not 2, 3, 5!!!)


class DWARF(DWARFFieldWriter):
    next_func_idx: int = 0

    unit_path: Path

    hir_functions: MutableSequence[Function | None]

    file_table: MutableMapping[Path, int]
    strings: DWARFStringPool

    writer: WriterProtocol

    _t_abbrev_compilation_unit = 1
    _t_abbrev_subprogram: int = 2
    _t_abbrev_base_type: int = 3
    _t_abbrev_variable: int = 4

    def trace_source_filepath(self, path: Path) -> int:
        path = path.absolute()
        if path in self.file_table:
            return self.file_table[path]

        self.file_table[path] = len(self.file_table) + 1
        definition = (
            self.file_table[path],
            f'"{path.parent.absolute()}"',
            f'"{path.name}"',
        )
        self.writer.directive("file", " ".join(map(str, definition)))
        return self.file_table[path]

    def trace_source_location(self, location: TokenLocation) -> None:
        assert location.filepath, (
            "Cannot trace source location: not a source code origin"
        )
        self.writer.dwarf_loc_directive(
            self.trace_source_filepath(location.filepath),
            location.line_number + 1,
            location.col_number + 1,
        )

    def trace_function_start(self, function: Function) -> None:
        self.hir_functions.append(function)
        self.writer.label(DW_LABEL_FUNC_BEGIN_FMT.format(self.next_func_idx))

    def trace_function_end(self) -> None:
        self.writer.label(DW_LABEL_FUNC_END_FMT.format(self.next_func_idx))
        self.next_func_idx += 1

    def write_full_dwarf_sections(self, module: Module) -> None:
        self._write_abbreviations()
        self._write_info_section(module)
        self._write_string_pool()

    def __init__(self, writer: "WriterProtocol", unit_path: Path) -> None:
        self.unit_path: Path = unit_path.absolute()

        self.writer = writer

        self.hir_functions = []

        self.strings = DWARFStringPool()
        self.file_table = {}

    def _get_loc_file_table_idx(self, location: TokenLocation) -> int:
        assert location.filepath
        return self.file_table[location.filepath.absolute()]

    def _write_string_pool(self) -> None:
        self.writer.section(SectionType.DWARF_STRINGS)
        for string in self.strings.pool:
            offset = self.strings.pool[string]
            self.string_definition(string, comment=f"String at offset {offset}")

    def _write_abbreviations(self) -> None:
        self.writer.section(SectionType.DWARF_ABBREV)
        self.writer.label(DW_LABEL_ABBREV)
        self.fielded_abbreviation(
            DWARF_COMPILE_UNIT_ABBREVIATION,
            self._t_abbrev_compilation_unit,
        )
        self.fielded_abbreviation(
            DWARF_SUBPROGRAM_ABBREVIATION,
            self._t_abbrev_subprogram,
        )
        self.fielded_abbreviation(
            DWARF_BASE_TYPE_ABBREVIATION,
            self._t_abbrev_base_type,
        )
        self.fielded_abbreviation(
            DWARF_VARIABLE_ABBREVIATION,
            self._t_abbrev_variable,
        )
        self.byte_field(0, comment="End of abbreviations listing")

    def _write_compilation_unit_header_die(self) -> None:
        self.writer.label(DW_LABEL_INFO)

        self.relative_offset_field(DW_LABEL_INFO_END, DW_LABEL_INFO_BEGIN)
        self.writer.label(DW_LABEL_INFO_BEGIN)

        self.short_field(4, comment="DWARF version 4")
        self.relative_offset_field(DW_LABEL_ABBREV, DW_LABEL_ABBREV)
        self.byte_field(8, comment="64-bit")

    def _write_info_section(self, module: Module) -> None:
        self.writer.section(SectionType.DWARF_INFO)

        self._write_compilation_unit_header_die()
        self._write_compilation_unit_die()

        self._write_base_types_die(module)
        self._write_subprograms_die()
        self._write_global_variables_die(module)
        self.byte_field(0, comment="End of  compilation unit")

        self.writer.label(DW_LABEL_INFO_END)

    def _write_base_types_die(self, module: Module) -> None:
        for name, base_type in module.types.items():
            if not isinstance(base_type, PrimitiveType):
                continue
            self.writer.label(f"Ltype_{name}")
            self.byte_field(
                self._t_abbrev_base_type,
                comment="Abbreviation DW_TAG_base_type",
            )
            self.strp_field(name, comment="DW_AT_name")

            encoding = self._encoding_from_gofra_primitive_type(base_type)
            self.byte_field(encoding, comment="DW_AT_encoding")
            self.byte_field(base_type.size_in_bytes, comment="DW_AT_byte_size")

    def _write_global_variables_die(self, module: Module) -> None:
        for variable in module.variables.values():
            if not isinstance(variable.type, PrimitiveType):
                continue

            self.byte_field(
                self._t_abbrev_variable,
                comment="Abbreviation DW_TAG_variable",
            )
            for attr, form in DWARF_VARIABLE_ABBREVIATION.fields:
                match attr:
                    case DWARFAttribute.DW_AT_external:
                        assert form == DWARFForm.DW_FORM_flag
                        self.byte_field(int(True), comment=attr.name)
                    case DWARFAttribute.DW_AT_name:
                        assert form == DWARFForm.DW_FORM_strp
                        self.strp_field(variable.name, comment=attr.name)
                    case DWARFAttribute.DW_AT_type:
                        assert form == DWARFForm.DW_FORM_ref4
                        self.relative_offset_field(
                            label_a="Ltype_int",
                            label_b=DW_LABEL_INFO,
                            comment=attr.name,
                        )
                    case DWARFAttribute.DW_AT_location:
                        assert form == DWARFForm.DW_FORM_exprloc
                        self.byte_field(9, comment=attr.name)
                        self.byte_field(3, comment=attr.name)
                        self.addr_field(variable.name, comment=attr.name)
                    case DWARFAttribute.DW_AT_declaration_line:
                        assert form == DWARFForm.DW_FORM_data1
                        self.byte_field(
                            variable.defined_at.line_number,
                            comment=attr.name,
                        )
                    case DWARFAttribute.DW_AT_declaration_file:
                        assert form == DWARFForm.DW_FORM_data1
                        declaration_file_idx = self._get_loc_file_table_idx(
                            variable.defined_at,
                        )
                        self.byte_field(declaration_file_idx, comment=attr.name)
                    case _:
                        raise NotImplementedError(attr, form)

    def _write_local_variables_children_die(self, function: Function) -> bool:
        has_children: bool = False
        for variable in function.variables.values():
            if not isinstance(variable.type, PrimitiveType):
                continue

            has_children = True
            self.byte_field(
                self._t_abbrev_variable,
                comment="Abbreviation DW_TAG_variable",
            )
            for attr, form in DWARF_VARIABLE_ABBREVIATION.fields:
                match attr:
                    case DWARFAttribute.DW_AT_external:
                        assert form == DWARFForm.DW_FORM_flag
                        self.byte_field(int(False), comment=attr.name)
                    case DWARFAttribute.DW_AT_name:
                        assert form == DWARFForm.DW_FORM_strp
                        self.strp_field(variable.name, comment=attr.name)
                    case DWARFAttribute.DW_AT_type:
                        assert form == DWARFForm.DW_FORM_ref4
                        self.relative_offset_field(
                            label_a="Ltype_int",
                            label_b=DW_LABEL_INFO,
                            comment=attr.name,
                        )
                    case DWARFAttribute.DW_AT_location:
                        assert form == DWARFForm.DW_FORM_exprloc
                        self.byte_field(1, comment=attr.name)
                        self.byte_field(0x50, comment=attr.name)
                    case DWARFAttribute.DW_AT_declaration_line:
                        assert form == DWARFForm.DW_FORM_data1
                        self.byte_field(
                            variable.defined_at.line_number,
                            comment=attr.name,
                        )
                    case DWARFAttribute.DW_AT_declaration_file:
                        assert form == DWARFForm.DW_FORM_data1
                        declaration_file_idx = self._get_loc_file_table_idx(
                            variable.defined_at,
                        )
                        self.byte_field(declaration_file_idx, comment=attr.name)
                    case _:
                        raise NotImplementedError(attr, form)
        return has_children

    def _encoding_from_gofra_primitive_type(self, t: PrimitiveType) -> DWARFEncoding:
        if isinstance(t, BoolType):
            return DWARFEncoding.DW_ATE_boolean
        if isinstance(t, CharType):
            return DWARFEncoding.DW_ATE_signed_char
        if isinstance(t, VoidType):
            return DWARFEncoding.DW_ATE_address
        if t.is_fp:
            return DWARFEncoding.DW_ATE_float

        return DWARFEncoding.DW_ATE_signed

    def _write_subprograms_die(self) -> None:
        for dw_pc_idx, hir in enumerate(self.hir_functions):
            if hir is None:
                continue

            assert hir.defined_at.filepath

            declaration_file_idx = self._get_loc_file_table_idx(hir.defined_at)

            self.byte_field(
                self._t_abbrev_subprogram,
                comment="Abbreviation DW_TAG_subprogram",
            )

            for attr, form in DWARF_SUBPROGRAM_ABBREVIATION.fields:
                match attr:
                    case DWARFAttribute.DW_AT_low_pc:
                        assert form == DWARFForm.DW_FORM_addr
                        low_pc_label = DW_LABEL_FUNC_BEGIN_FMT.format(dw_pc_idx)
                        self.addr_field(low_pc_label, comment=attr.name)
                    case DWARFAttribute.DW_AT_high_pc:
                        assert form == DWARFForm.DW_FORM_addr
                        high_pc_label = DW_LABEL_FUNC_END_FMT.format(dw_pc_idx)
                        self.addr_field(high_pc_label, comment=attr.name)
                    case DWARFAttribute.DW_AT_name:
                        assert form == DWARFForm.DW_FORM_strp
                        self.strp_field(hir.name, comment=attr.name)
                    case DWARFAttribute.DW_AT_declaration_file:
                        assert form == DWARFForm.DW_FORM_data1
                        self.byte_field(declaration_file_idx, comment=attr.name)
                    case DWARFAttribute.DW_AT_declaration_line:
                        assert form == DWARFForm.DW_FORM_data1
                        self.byte_field(hir.defined_at.line_number, comment=attr.name)
                    case DWARFAttribute.DW_AT_external:
                        assert form == DWARFForm.DW_FORM_flag
                        self.byte_field(int(hir.is_external), comment=attr.name)
                    case _:
                        raise NotImplementedError(attr, form)

            self._write_local_variables_children_die(hir)
            self.byte_field(0, comment="End of abbreviation children")

    def _write_compilation_unit_die(self) -> None:
        self.byte_field(
            self._t_abbrev_compilation_unit,
            comment="Abbreviation DW_TAG_compile_unit",
        )
        self.strp_field(DWARF_PRODUCER_STRING, comment="DW_AT_producer")
        self.short_field(DW_LANGUAGE_GOFRA, comment="DW_AT_language")

        self.strp_field(self.unit_path.name, comment="DW_AT_name")
        self.long_field(0, comment="DW_AT_stmt_list")
        self.strp_field(str(self.unit_path.parent), comment="DW_AT_comp_dir")

        low_pc_label = DW_LABEL_FUNC_BEGIN_FMT.format(0)
        high_pc_label = DW_LABEL_FUNC_END_FMT.format(self.next_func_idx - 1)
        self.addr_field(low_pc_label, comment="DW_AT_low_pc")
        self.addr_field(high_pc_label, comment="DW_AT_high_pc")
