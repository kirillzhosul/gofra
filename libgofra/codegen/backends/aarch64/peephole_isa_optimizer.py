from libgofra.codegen.backends.aarch64.writer import (
    AARCH64BufferedWriterImplementation,
    CISLine,
)


def peephole_isa_optimizer_pass(writer: AARCH64BufferedWriterImplementation) -> None:
    optimized: list[CISLine] = []

    idx = 0
    while idx < len(writer.buffer):
        optimized_item, skip = _try_optimize_at(writer.buffer, idx)

        if optimized_item:
            optimized.append(optimized_item)
        idx += skip

    writer.buffer = optimized


def _try_optimize_at(buffer: list[CISLine], idx: int) -> tuple[CISLine | None, int]:
    if idx + 1 >= len(buffer):
        return buffer[idx], 1

    item1 = buffer[idx]
    item2 = buffer[idx + 1]

    if (
        item1.type == "instruction"
        and item2.type == "instruction"
        and item1.text.startswith("str ")
        and item2.text.startswith("ldr ")
        and "X" in item1.text
        and "X" in item2.text
    ):
        reg1 = item1.text.split()[1][:-1]
        reg2 = item2.text.split()[1][:-1]

        dest1 = " ".join(item1.text.split()[2:])
        dest2 = " ".join(item2.text.split()[2:])

        assert dest1 == "[SP, -16]!"
        assert dest2 == "[SP], #16"
        if reg1 == reg2:
            return CISLine(
                type="comment",
                text="// optimized by peephole [pattern: redundant push-pop stack]",
            ), 2

    return buffer[idx], 1
