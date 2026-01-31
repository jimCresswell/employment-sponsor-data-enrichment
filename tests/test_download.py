"""Tests for download stage with filesystem injection."""

from pathlib import Path

from uk_sponsor_pipeline.stages.download import download_latest


def test_download_with_in_memory_fs(in_memory_fs):
    csv_content = (
        b"Organisation Name,Town/City,County,Type & Rating,Route\n"
        b"Acme Ltd,London,Greater London,A rating,Skilled Worker\n"
    )

    class DummyResponse:
        def __init__(self, content: bytes) -> None:
            self.content = content
            self.status_code = 200

        def raise_for_status(self) -> None:
            return None

    class DummySession:
        def __init__(self, response):
            self.response = response
            self.calls = []

        def get(self, url, timeout=None, stream=None):
            self.calls.append(url)
            return self.response

    session = DummySession(DummyResponse(csv_content))

    result = download_latest(
        url_override="https://example.com/register.csv",
        data_dir="data/raw",
        reports_dir="reports",
        session=session,
        fs=in_memory_fs,
    )

    assert in_memory_fs.read_bytes(result.output_path) == csv_content
    manifest = in_memory_fs.read_json(Path("reports") / "download_manifest.json")
    assert manifest["schema_valid"] is True
    assert manifest["asset_url"] == "https://example.com/register.csv"
