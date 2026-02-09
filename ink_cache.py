"""
Ink data caching to avoid repeated API calls
"""
import json
import os
from typing import List, Dict, Optional
from datetime import datetime


CACHE_FILE = "ink_cache.json"


def save_inks_to_cache(inks: List[Dict]) -> None:
    """
    Save fetched inks to disk cache.

    Args:
        inks: List of ink dictionaries
    """
    cache_data = {
        "timestamp": datetime.now().isoformat(),
        "ink_count": len(inks),
        "inks": inks
    }

    with open(CACHE_FILE, "w") as f:
        json.dump(cache_data, f, indent=2)


def load_inks_from_cache() -> Optional[Dict]:
    """
    Load inks from disk cache.

    Returns:
        Dictionary with timestamp, ink_count, and inks list if cache exists, None otherwise
    """
    if not os.path.exists(CACHE_FILE):
        return None

    try:
        with open(CACHE_FILE, "r") as f:
            cache_data = json.load(f)
            return cache_data
    except (json.JSONDecodeError, IOError):
        return None


def get_cache_info() -> Optional[str]:
    """
    Get human-readable cache information.

    Returns:
        String describing cache status, or None if no cache
    """
    cache = load_inks_from_cache()
    if not cache:
        return None

    timestamp = cache.get("timestamp", "Unknown")
    ink_count = cache.get("ink_count", 0)

    # Parse timestamp
    try:
        dt = datetime.fromisoformat(timestamp)
        time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        time_str = timestamp

    return f"Cached: {ink_count} inks from {time_str}"


def clear_cache() -> bool:
    """
    Delete the cache file.

    Returns:
        True if cache was deleted, False if no cache existed
    """
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
        return True
    return False
