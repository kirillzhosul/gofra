"""DWARF debug information generator."""

from collections.abc import MutableMapping, MutableSequence
from pathlib import Path

from libgofra.codegen.backends.aarch64.writer import WriterProtocol
from libgofra.codegen.dwarf.abbreviations import (
    DWARF_COMPILE_UNIT_ABBREVIATION,
    DWARF_SUBPROGRAM_ABBREVIATION,
)
from libgofra.codegen.dwarf.labels import (
    DW_LABEL_ABBREV,
    DW_LABEL_FUNC_BEGIN_FMT,
    DW_LABEL_FUNC_END_FMT,
    DW_LABEL_INFO_BEGIN,
    DW_LABEL_INFO_END,
)
from libgofra.codegen.dwarf.opcodes import DW_LANGUAGE_GOFRA
from libgofra.codegen.dwarf.strings import DWARF_PRODUCER_STRING, DWARFStringPool
from libgofra.codegen.dwarf.writer import DWARFFieldWriter
from libgofra.codegen.sections._factory import SectionType
from libgofra.hir.function import Function
from libgofra.lexer.tokens import TokenLocation


class DWARF(DWARFFieldWriter):
    next_func_idx: int = 0

    unit_path: Path

    hir_functions: MutableSequence[Function | None]

    file_table: MutableMapping[Path, int]
    strings: DWARFStringPool

    writer: WriterProtocol

    def trace_source_filepath(self, path: Path) -> int:
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

    def write_full_dwarf_sections(self) -> None:
        self._write_abbreviations()
        self._write_info_section()
        self._write_string_pool()

    def __init__(self, writer: "WriterProtocol", unit_path: Path) -> None:
        self.unit_path: Path = unit_path.absolute()

        self.writer = writer

        self.hir_functions = []

        self.strings = DWARFStringPool()
        self.file_table = {}

    def _write_string_pool(self) -> None:
        self.writer.section(SectionType.DWARF_STRINGS)
        for string in self.strings.pool:
            offset = self.strings.pool[string]
            self.string_definition(string, comment=f"String at offset {offset}")

    def _write_abbreviations(self) -> None:
        self.writer.section(SectionType.DWARF_ABBREV)
        self.writer.label(DW_LABEL_ABBREV)
        self.fielded_abbreviation(DWARF_COMPILE_UNIT_ABBREVIATION, 1)
        self.fielded_abbreviation(DWARF_SUBPROGRAM_ABBREVIATION, 2)
        self.byte_field(0, comment="End of abbreviations listing")

    def _write_compilation_unit_header_die(self) -> None:
        self.relative_offset_field(DW_LABEL_INFO_END, DW_LABEL_INFO_BEGIN)
        self.writer.label(DW_LABEL_INFO_BEGIN)

        self.short_field(4, comment="DWARF version 4")
        self.relative_offset_field(DW_LABEL_ABBREV, DW_LABEL_ABBREV)
        self.byte_field(8, comment="64-bit")

    def _write_info_section(self) -> None:
        self.writer.section(SectionType.DWARF_INFO)

        self._write_compilation_unit_header_die()
        self._write_compilation_unit_die()
        self._write_subprograms_die()
        self.byte_field(0, comment="End of info")

        self.writer.label(DW_LABEL_INFO_END)

    def _write_subprograms_die(self) -> None:
        for dw_pc_idx, hir in enumerate(self.hir_functions):
            if hir is None:
                continue

            assert hir.defined_at.filepath

            declaration_file_idx = self.file_table[hir.defined_at.filepath]
            low_pc_label = DW_LABEL_FUNC_BEGIN_FMT.format(dw_pc_idx)
            high_pc_label = DW_LABEL_FUNC_END_FMT.format(dw_pc_idx)

            self.byte_field(2, comment="Abbreviation DW_TAG_subprogram")
            self.addr_field(low_pc_label, comment="DW_AT_low_pc")
            self.addr_field(high_pc_label, comment="DW_AT_high_pc")
            self.strp_field(hir.name, comment="DW_AT_name")
            self.byte_field(declaration_file_idx, comment="DW_AT_decl_file")
            self.byte_field(hir.defined_at.line_number, comment="DW_AT_decl_line")
            self.byte_field(int(hir.is_external), comment="DW_AT_external")

            self.byte_field(0, comment="End of abbreviation children")

    def _write_compilation_unit_die(self) -> None:
        self.byte_field(1, comment="Abbreviation DW_TAG_compile_unit")
        self.strp_field(DWARF_PRODUCER_STRING, comment="DW_AT_producer")
        self.short_field(DW_LANGUAGE_GOFRA, comment="DW_AT_language")

        self.strp_field(self.unit_path.name, comment="DW_AT_name")
        self.long_field(0, comment="DW_AT_stmt_list")
        self.strp_field(str(self.unit_path.parent), comment="DW_AT_comp_dir")

        low_pc_label = DW_LABEL_FUNC_BEGIN_FMT.format(0)
        high_pc_label = DW_LABEL_FUNC_END_FMT.format(self.next_func_idx - 1)
        self.addr_field(low_pc_label, comment="DW_AT_low_pc")
        self.addr_field(high_pc_label, comment="DW_AT_high_pc")
