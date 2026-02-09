"""
Test script for ink cache functionality
"""
from ink_cache import save_inks_to_cache, load_inks_from_cache, get_cache_info, clear_cache

# Test data
test_inks = [
    {"name": "Test Ink 1", "brand_name": "Test Brand", "color": "#0000ff"},
    {"name": "Test Ink 2", "brand_name": "Test Brand", "color": "#ff0000"},
]

print("Testing ink cache...")

# Clear any existing cache
clear_cache()
print("✓ Cleared old cache")

# Test saving
save_inks_to_cache(test_inks)
print("✓ Saved test inks to cache")

# Test loading
cache = load_inks_from_cache()
assert cache is not None, "Cache should exist"
assert cache["ink_count"] == 2, "Should have 2 inks"
assert len(cache["inks"]) == 2, "Should have 2 inks in list"
print("✓ Loaded inks from cache")

# Test cache info
info = get_cache_info()
assert info is not None, "Cache info should exist"
print(f"✓ Cache info: {info}")

# Clean up
clear_cache()
print("✓ Cleaned up test cache")

print("\n✅ All cache tests passed!")
