"""Tests for cache infrastructure components."""

from pathlib import Path

from uk_sponsor_pipeline.infrastructure import DiskCache


class TestDiskCache:
    """Tests for DiskCache."""

    def test_get_returns_none_for_missing_key(self, tmp_path: Path) -> None:
        """get() returns None for missing key."""
        cache = DiskCache(tmp_path / "cache")
        assert cache.get("nonexistent") is None

    def test_set_and_get_roundtrip(self, tmp_path: Path) -> None:
        """set() and get() roundtrip works correctly."""
        cache = DiskCache(tmp_path / "cache")
        cache.set("mykey", {"test": "value", "number": 42})
        result = cache.get("mykey")
        assert result == {"test": "value", "number": 42}

    def test_has_returns_correct_values(self, tmp_path: Path) -> None:
        """has() returns correct boolean values."""
        cache = DiskCache(tmp_path / "cache")
        assert cache.has("missing") is False
        cache.set("exists", {"data": True})
        assert cache.has("exists") is True
