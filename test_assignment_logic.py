"""
Tests for ink assignment logic
"""
import pytest
from assignment_logic import (
    parse_swatch_date_from_comment,
    get_month_summary,
    parse_comment_json,
    has_assignment,
    find_ink_by_name,
    search_inks,
)


def test_get_month_summary():
    """Test extracting inks for a specific month"""
    # Manually create assignments for January 2025
    assignments = {
        "2025-01-01": 0,
        "2025-01-15": 1,
        "2025-01-31": 2,
        "2025-02-01": 3,  # Different month
    }

    # Get January inks
    january_inks = get_month_summary(assignments, 2025, 1)

    # Should have 3 January assignments
    assert len(january_inks) == 3
    assert set(january_inks) == {0, 1, 2}


def test_get_month_summary_february():
    """Test February summary"""
    assignments = {
        "2025-01-31": 0,
        "2025-02-01": 1,
        "2025-02-14": 2,
        "2025-02-28": 3,
        "2025-03-01": 4,
    }

    # Get February inks
    february_inks = get_month_summary(assignments, 2025, 2)

    # Should have 3 February assignments
    assert len(february_inks) == 3
    assert set(february_inks) == {1, 2, 3}


def test_get_month_summary_empty():
    """Test month summary with no assignments"""
    assignments = {}
    january_inks = get_month_summary(assignments, 2025, 1)

    assert january_inks == []


def test_get_month_summary_wrong_year():
    """Test month summary filters by year correctly"""
    assignments = {
        "2024-01-15": 0,  # Wrong year
        "2025-01-15": 1,  # Right year
    }

    january_inks = get_month_summary(assignments, 2025, 1)

    assert len(january_inks) == 1
    assert january_inks[0] == 1


def test_parse_swatch_date_from_comment_valid():
    """Test parsing valid swatch date from comment (new format with theme)"""
    comment = '{"swatch2026": {"theme": "All samples", "theme_description": "New inks for a new year", "date": "2026-01-15"}}'
    date_str = parse_swatch_date_from_comment(comment, 2026)

    assert date_str == "2026-01-15"


def test_parse_swatch_date_from_comment_wrong_year():
    """Test parsing swatch date for wrong year returns None"""
    comment = '{"swatch2026": "2026-01-15"}'
    date_str = parse_swatch_date_from_comment(comment, 2025)

    assert date_str is None


def test_parse_swatch_date_from_comment_invalid_json():
    """Test parsing invalid JSON returns None"""
    comment = 'not valid json'
    date_str = parse_swatch_date_from_comment(comment, 2026)

    assert date_str is None


def test_parse_swatch_date_from_comment_empty():
    """Test parsing empty comment returns None"""
    date_str = parse_swatch_date_from_comment("", 2026)

    assert date_str is None


def test_parse_swatch_date_from_comment_no_swatch_key():
    """Test parsing JSON without swatch key returns None"""
    comment = '{"other_field": "value"}'
    date_str = parse_swatch_date_from_comment(comment, 2026)

    assert date_str is None


def test_parse_swatch_date_from_comment_new_format_missing_date():
    """Test parsing new format without date field returns None"""
    comment = '{"swatch2026": {"theme": "All samples", "theme_description": "New inks"}}'
    date_str = parse_swatch_date_from_comment(comment, 2026)

    assert date_str is None


def test_parse_swatch_date_from_comment_new_format_invalid_date():
    """Test parsing new format with invalid date returns None"""
    comment = '{"swatch2026": {"theme": "All samples", "date": "not-a-date"}}'
    date_str = parse_swatch_date_from_comment(comment, 2026)

    assert date_str is None


# =============================================================================
# Tests for new pure helper functions
# =============================================================================

def test_parse_comment_json_valid():
    """Test parsing valid JSON comment"""
    result = parse_comment_json('{"key": "value"}')
    assert result == {"key": "value"}


def test_parse_comment_json_empty():
    """Test parsing empty/None comment"""
    assert parse_comment_json("") == {}
    assert parse_comment_json(None) == {}


def test_parse_comment_json_invalid():
    """Test parsing invalid JSON"""
    assert parse_comment_json("not json") == {}


def test_has_assignment_true():
    """Test has_assignment returns True when date exists"""
    ink = {"private_comment": '{"swatch2025": {"date": "2025-01-15"}}'}
    assert has_assignment(ink, 2025) is True


def test_has_assignment_false_no_comment():
    """Test has_assignment returns False when no comment"""
    ink = {"private_comment": ""}
    assert has_assignment(ink, 2025) is False


def test_has_assignment_false_wrong_year():
    """Test has_assignment returns False for wrong year"""
    ink = {"private_comment": '{"swatch2024": {"date": "2024-01-15"}}'}
    assert has_assignment(ink, 2025) is False


def test_has_assignment_false_no_date():
    """Test has_assignment returns False when no date field"""
    ink = {"private_comment": '{"swatch2025": {"theme": "Test"}}'}
    assert has_assignment(ink, 2025) is False


def test_find_ink_by_name_exact_match():
    """Test finding ink by exact name match"""
    inks = [
        {"brand_name": "Diamine", "name": "Blue Velvet"},
        {"brand_name": "Pilot", "name": "Blue"},
    ]
    result = find_ink_by_name("Blue Velvet", inks)
    assert result is not None
    assert result[0] == 0


def test_find_ink_by_name_full_name():
    """Test finding ink by brand + name"""
    inks = [
        {"brand_name": "Diamine", "name": "Blue Velvet"},
        {"brand_name": "Pilot", "name": "Blue"},
    ]
    result = find_ink_by_name("diamine blue velvet", inks)
    assert result is not None
    assert result[0] == 0


def test_find_ink_by_name_substring():
    """Test finding ink by substring"""
    inks = [
        {"brand_name": "Diamine", "name": "Blue Velvet"},
        {"brand_name": "Pilot", "name": "Iroshizuku Kon-peki"},
    ]
    result = find_ink_by_name("velvet", inks)
    assert result is not None
    assert result[0] == 0


def test_find_ink_by_name_not_found():
    """Test finding ink that doesn't exist"""
    inks = [
        {"brand_name": "Diamine", "name": "Blue Velvet"},
    ]
    result = find_ink_by_name("Red Dragon", inks)
    assert result is None


def test_search_inks_by_query():
    """Test searching inks by name query"""
    inks = [
        {"brand_name": "Diamine", "name": "Blue Velvet", "cluster_tags": ["blue"]},
        {"brand_name": "Pilot", "name": "Red Dragon", "cluster_tags": ["red"]},
    ]
    results = search_inks(inks, 2025, query="blue")
    assert len(results) == 1
    assert results[0]["name"] == "Blue Velvet"


def test_search_inks_by_color():
    """Test searching inks by color tag"""
    inks = [
        {"brand_name": "Diamine", "name": "Blue Velvet", "cluster_tags": ["blue"], "private_comment": ""},
        {"brand_name": "Pilot", "name": "Red Dragon", "cluster_tags": ["red"], "private_comment": ""},
    ]
    results = search_inks(inks, 2025, color="red")
    assert len(results) == 1
    assert results[0]["name"] == "Red Dragon"


def test_search_inks_by_brand():
    """Test searching inks by brand"""
    inks = [
        {"brand_name": "Diamine", "name": "Blue Velvet", "cluster_tags": [], "private_comment": ""},
        {"brand_name": "Pilot", "name": "Blue", "cluster_tags": [], "private_comment": ""},
    ]
    results = search_inks(inks, 2025, brand="pilot")
    assert len(results) == 1
    assert results[0]["brand"] == "Pilot"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
