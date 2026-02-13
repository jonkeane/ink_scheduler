"""
Tests for ink cache functionality.

Uses pytest fixtures to test in a temp directory, keeping the real cache safe.
"""
import pytest
import os
from ink_cache import save_inks_to_cache, load_inks_from_cache, get_cache_info, clear_cache
import ink_cache


@pytest.fixture
def temp_cache(tmp_path, monkeypatch):
    """Use a temporary directory for cache operations."""
    cache_file = tmp_path / "ink_cache.json"
    monkeypatch.setattr(ink_cache, "CACHE_FILE", str(cache_file))
    return cache_file


@pytest.fixture
def test_inks():
    """Sample ink data for testing."""
    return [
        {"name": "Test Ink 1", "brand_name": "Test Brand", "color": "#0000ff"},
        {"name": "Test Ink 2", "brand_name": "Test Brand", "color": "#ff0000"},
    ]


def test_save_and_load_cache(temp_cache, test_inks):
    """Test saving inks to cache and loading them back."""
    save_inks_to_cache(test_inks)

    cache = load_inks_from_cache()
    assert cache is not None, "Cache should exist after saving"
    assert cache["ink_count"] == 2
    assert len(cache["inks"]) == 2
    assert cache["inks"][0]["name"] == "Test Ink 1"
    assert cache["inks"][1]["name"] == "Test Ink 2"


def test_load_nonexistent_cache(temp_cache):
    """Test loading when no cache exists."""
    cache = load_inks_from_cache()
    assert cache is None


def test_get_cache_info(temp_cache, test_inks):
    """Test getting human-readable cache info."""
    # No cache yet
    info = get_cache_info()
    assert info is None

    # After saving
    save_inks_to_cache(test_inks)
    info = get_cache_info()
    assert info is not None
    assert "2 inks" in info


def test_clear_cache(temp_cache, test_inks):
    """Test clearing the cache."""
    # Clear nonexistent cache returns False
    assert clear_cache() is False

    # Save then clear
    save_inks_to_cache(test_inks)
    assert os.path.exists(temp_cache)

    assert clear_cache() is True
    assert not os.path.exists(temp_cache)


def test_cache_preserves_all_fields(temp_cache):
    """Test that cache preserves all ink fields."""
    inks = [
        {
            "name": "Complex Ink",
            "brand_name": "Fancy Brand",
            "color": "#123456",
            "cluster_tags": ["blue", "dark"],
            "comment": '{"swatch": {"date": "2026-01-15"}}',
            "extra_field": "should be preserved"
        }
    ]

    save_inks_to_cache(inks)
    cache = load_inks_from_cache()

    loaded_ink = cache["inks"][0]
    assert loaded_ink["name"] == "Complex Ink"
    assert loaded_ink["cluster_tags"] == ["blue", "dark"]
    assert loaded_ink["extra_field"] == "should be preserved"
