"""Tests for in-memory filesystem handle helpers."""

from pathlib import Path

from tests.fakes import InMemoryFileSystem


class TestInMemoryFileSystemOpenHandles:
    """Validate open handle persistence in the in-memory filesystem."""

    def test_open_text_write_persists_on_close(self) -> None:
        fs = InMemoryFileSystem()
        path = Path("data/tmp/example.txt")

        with fs.open_text(path, mode="w", encoding="utf-8", newline="") as handle:
            handle.write("first line")
            handle.write("\n")
            handle.write("second line")

        assert fs.read_text(path) == "first line\nsecond line"

    def test_open_text_append_preserves_existing_content(self) -> None:
        fs = InMemoryFileSystem()
        path = Path("data/tmp/example.txt")
        fs.write_text("alpha", path)

        with fs.open_text(path, mode="a", encoding="utf-8", newline="") as handle:
            handle.write("\nbeta")

        assert fs.read_text(path) == "alpha\nbeta"

    def test_open_binary_write_persists_on_close(self) -> None:
        fs = InMemoryFileSystem()
        path = Path("data/tmp/data.bin")

        with fs.open_binary(path, mode="wb") as handle:
            handle.write(b"\x10\x20")
            handle.write(b"\x30")

        assert fs.read_bytes(path) == b"\x10\x20\x30"
