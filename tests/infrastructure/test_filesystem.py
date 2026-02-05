"""Tests for filesystem infrastructure components."""

from pathlib import Path

import pandas as pd

from uk_sponsor_pipeline.infrastructure import LocalFileSystem


class TestLocalFileSystemAppend:
    """Tests for LocalFileSystem append_csv."""

    def test_append_csv_writes_and_appends(self, tmp_path: Path) -> None:
        fs = LocalFileSystem()
        path = tmp_path / "out.csv"
        df1 = pd.DataFrame({"col": ["a"]})
        df2 = pd.DataFrame({"col": ["b"]})

        fs.append_csv(df1, path)
        fs.append_csv(df2, path)

        out = pd.read_csv(path, dtype=str).fillna("")
        assert out["col"].tolist() == ["a", "b"]


class TestLocalFileSystemWriteBytesStream:
    """Tests for LocalFileSystem write_bytes_stream."""

    def test_write_bytes_stream_writes_chunks_in_order(self, tmp_path: Path) -> None:
        fs = LocalFileSystem()
        path = tmp_path / "out.bin"

        def chunks() -> list[bytes]:
            return [b"alpha", b"-", b"beta"]

        fs.write_bytes_stream(path, chunks())

        assert path.read_bytes() == b"alpha-beta"
