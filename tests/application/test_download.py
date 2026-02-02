"""Tests for extract step with filesystem injection."""

from pathlib import Path

from tests.fakes import InMemoryFileSystem
from uk_sponsor_pipeline.application.extract import extract_register


def test_extract_with_in_memory_fs(in_memory_fs: InMemoryFileSystem) -> None:
    csv_content = (
        b"Organisation Name,Town/City,County,Type & Rating,Route\n"
        b"Acme Ltd,London,Greater London,A rating,Skilled Worker\n"
    )

    class DummyResponse:
        def __init__(self, content: bytes) -> None:
            self.content = content
            self.status_code = 200
            self.text = content.decode("utf-8", errors="ignore")

        def raise_for_status(self) -> None:
            return None

    class DummySession:
        def __init__(self, response: DummyResponse) -> None:
            self.response = response
            self.calls: list[str] = []

        def get_text(self, url: str, *, timeout_seconds: float) -> str:
            self.calls.append(url)
            return self.response.text

        def get_bytes(self, url: str, *, timeout_seconds: float) -> bytes:
            self.calls.append(url)
            return self.response.content

    session = DummySession(DummyResponse(csv_content))

    result = extract_register(
        url_override="https://example.com/register.csv",
        data_dir="data/raw",
        reports_dir="reports",
        session=session,
        fs=in_memory_fs,
    )

    assert in_memory_fs.read_bytes(result.output_path) == csv_content
    manifest = in_memory_fs.read_json(Path("reports") / "extract_manifest.json")
    assert isinstance(manifest.get("schema_valid"), bool)
    assert isinstance(manifest.get("asset_url"), str)
    assert manifest["schema_valid"] is True
    assert manifest["asset_url"] == "https://example.com/register.csv"
