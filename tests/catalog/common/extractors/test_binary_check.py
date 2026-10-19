"""Telling a binary file from a text file."""

from pathlib import Path

from klint.catalog.common.extractors.binary_check import is_likely_binary
from tests.support.builders import write_text


def test_file_is_binary_when_it_holds_a_nul_byte(tmp_path: Path) -> None:
    text_file = write_text(tmp_path / "notes.txt", "plain text\n")
    binary_file = tmp_path / "blob.dat"
    binary_file.write_bytes(b"\x00\x01\x02")

    assert not is_likely_binary(text_file)
    assert is_likely_binary(binary_file)
