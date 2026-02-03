from libgofra.codegen.backends.aarch64.writer import WriterProtocol
from libgofra.codegen.dwarf.abbreviations import DWARFAbbreviation
from libgofra.codegen.dwarf.opcodes import DWARFAttribute, DWARFForm
from libgofra.codegen.dwarf.strings import DWARFStringPool


class DWARFFieldWriter:
    writer: WriterProtocol
    strings: DWARFStringPool

    def form_field(self, form: DWARFForm) -> None:
        self.byte_field(form.value, comment=form.name)

    def byte_field(self, value: int, *, comment: str | None = None) -> None:
        return self.writer.sym_sect_directive("byte", value, comment=comment)

    def short_field(self, value: int, *, comment: str | None = None) -> None:
        return self.writer.sym_sect_directive("short", value, comment=comment)

    def long_field(self, value: int, *, comment: str | None = None) -> None:
        return self.writer.sym_sect_directive("long", value, comment=comment)

    def addr_field(self, label: str, *, comment: str | None = None) -> None:
        return self.writer.sym_sect_directive("quad", label, comment=comment)

    def string_definition(self, string: str, *, comment: str | None = None) -> None:
        return self.writer.sym_sect_directive("asciz", f'"{string}"', comment=comment)

    def relative_offset_field(
        self,
        label_a: str,
        label_b: str,
        *,
        comment: str | None = None,
    ) -> None:
        return self.writer.sym_sect_directive(
            "long",
            f"{label_a} - {label_b}",
            comment=comment,
        )

    def strp_field(self, string: str, *, comment: str | None = None) -> None:
        return self.writer.sym_sect_directive(
            "long",
            self.strings.load(string),
            comment=comment,
        )

    def attribute_field(self, attribute: DWARFAttribute) -> None:
        self.byte_field(attribute.value, comment=attribute.name)

    def fielded_abbreviation(self, abbreviation: DWARFAbbreviation, idx: int) -> None:
        self.byte_field(idx, comment=f"Abbreviation {idx} [{abbreviation.tag.name}]")
        self.byte_field(abbreviation.tag, comment=abbreviation.tag.name)
        self.byte_field(int(abbreviation.has_children), comment="Has children")

        for attribute, form in abbreviation.fields:
            self.attribute_field(attribute)
            self.form_field(form)

        self.byte_field(0, comment=f"End of abbreviation {idx}")
        self.byte_field(0, comment=f"End of abbreviation {idx}")
