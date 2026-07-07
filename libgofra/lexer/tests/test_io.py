from pathlib import Path

import pytest

from libgofra.lexer.errors import (
    IOFileDoesNotExistsError,
    IOFileNotAnFileError,
    IOFileNotAnTextFileError,
)
from libgofra.lexer.io import open_source_file, open_source_file_line_stream


def test_open_source_file_reads_utf8_text(tmp_path: Path) -> None:
    source_path = tmp_path / "example.gof"
    source_text = "print('hello')\nprint('world')\n"
    source_path.write_text(source_text, encoding="utf-8")

    with open_source_file(source_path) as stream:
        assert stream.read() == source_text


def test_open_source_file_line_stream_yields_all_lines(tmp_path: Path) -> None:
    source_path = tmp_path / "example.gof"
    source_path.write_text("line1\nline2\n", encoding="utf-8")

    lines = list(open_source_file_line_stream(source_path))
    assert lines == ["line1\n", "line2\n"]


def test_open_source_file_raises_when_file_missing(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.gof"

    with pytest.raises(IOFileDoesNotExistsError):
        open_source_file(missing_path)


def test_open_source_file_raises_when_path_is_directory(tmp_path: Path) -> None:
    dir_path = tmp_path / "dir"
    dir_path.mkdir()

    with pytest.raises(IOFileNotAnFileError):
        open_source_file(dir_path)


def test_open_source_file_line_stream_raises_on_invalid_utf8(tmp_path: Path) -> None:
    source_path = tmp_path / "invalid.gof"
    source_path.write_bytes(b"\xff\xfe\xfa")

    with pytest.raises(IOFileNotAnTextFileError):
        list(open_source_file_line_stream(source_path))
