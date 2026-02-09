"""
Tests for ink assignment logic
"""
import pytest
from datetime import datetime
from assignment_logic import (
    create_yearly_assignments,
    create_yearly_assignments_with_inks,
    parse_swatch_date_from_comment,
    get_month_summary,
    validate_assignments_unique
)


def test_create_yearly_assignments_basic():
    """Test basic yearly assignment creation"""
    # Test with 100 inks for year 2025
    assignments = create_yearly_assignments(100, 2025, seed=42)

    # Should have 100 assignments (one per ink)
    assert len(assignments) == 100

    # All should be in 2025
    for date_str in assignments.keys():
        date = datetime.strptime(date_str, "%Y-%m-%d")
        assert date.year == 2025

    # All inks should be unique
    assert validate_assignments_unique(assignments)


def test_create_yearly_assignments_empty():
    """Test with no inks"""
    assignments = create_yearly_assignments(0, 2025)
    assert assignments == {}


def test_create_yearly_assignments_more_than_days():
    """Test with more inks than days in year"""
    # 365 days in 2025, but 400 inks
    assignments = create_yearly_assignments(400, 2025, seed=42)

    # Should only assign 365 inks (one per day)
    assert len(assignments) == 365

    # All inks should be unique
    assert validate_assignments_unique(assignments)


def test_create_yearly_assignments_fewer_than_days():
    """Test with fewer inks than days in year"""
    # Only 100 inks but 365 days
    assignments = create_yearly_assignments(100, 2025, seed=42)

    # Should assign all 100 inks
    assert len(assignments) == 100

    # All inks should be unique
    assert validate_assignments_unique(assignments)


def test_create_yearly_assignments_reproducible():
    """Test that same seed produces same assignments"""
    assignments1 = create_yearly_assignments(50, 2025, seed=123)
    assignments2 = create_yearly_assignments(50, 2025, seed=123)

    assert assignments1 == assignments2


def test_create_yearly_assignments_different_with_different_seed():
    """Test that different seeds produce different assignments"""
    assignments1 = create_yearly_assignments(50, 2025, seed=123)
    assignments2 = create_yearly_assignments(50, 2025, seed=456)

    # Should be different (extremely unlikely to be the same)
    assert assignments1 != assignments2


def test_get_month_summary():
    """Test extracting inks for a specific month"""
    # Create assignments for 365 inks in 2025
    assignments = create_yearly_assignments(365, 2025, seed=42)

    # Get January inks
    january_inks = get_month_summary(assignments, 2025, 1)

    # January has 31 days, so should have 31 inks
    assert len(january_inks) == 31

    # All should be valid ink indices
    for ink_idx in january_inks:
        assert 0 <= ink_idx < 365


def test_get_month_summary_february():
    """Test February which has fewer days"""
    assignments = create_yearly_assignments(365, 2025, seed=42)

    # Get February inks (28 days in 2025)
    february_inks = get_month_summary(assignments, 2025, 2)

    # Should have 28 inks
    assert len(february_inks) == 28


def test_get_month_summary_empty():
    """Test month summary with no assignments"""
    assignments = {}
    january_inks = get_month_summary(assignments, 2025, 1)

    assert january_inks == []


def test_validate_assignments_unique_valid():
    """Test validation with unique assignments"""
    assignments = {
        "2025-01-01": 0,
        "2025-01-02": 1,
        "2025-01-03": 2,
    }

    assert validate_assignments_unique(assignments) is True


def test_validate_assignments_unique_duplicate():
    """Test validation with duplicate ink"""
    assignments = {
        "2025-01-01": 0,
        "2025-01-02": 1,
        "2025-01-03": 0,  # Duplicate!
    }

    assert validate_assignments_unique(assignments) is False


def test_validate_assignments_unique_empty():
    """Test validation with empty assignments"""
    assignments = {}

    assert validate_assignments_unique(assignments) is True


def test_year_coverage():
    """Test that assignments cover the whole year when enough inks"""
    assignments = create_yearly_assignments(365, 2025, seed=42)

    # Extract all months
    months_with_inks = set()
    for date_str in assignments.keys():
        date = datetime.strptime(date_str, "%Y-%m-%d")
        months_with_inks.add(date.month)

    # Should have inks in all 12 months
    assert months_with_inks == set(range(1, 13))


def test_parse_swatch_date_from_comment_valid_old_format():
    """Test parsing valid swatch date from comment (old format)"""
    comment = '{"swatch2026": "2026-01-15"}'
    date_str = parse_swatch_date_from_comment(comment, 2026)

    assert date_str == "2026-01-15"


def test_parse_swatch_date_from_comment_valid_new_format():
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


def test_create_yearly_assignments_with_inks_explicit_dates():
    """Test that explicit dates in comments are respected (new format)"""
    inks = [
        {"name": "Ink 1", "comment": '{"swatch2025": {"theme": "New Year", "date": "2025-01-01"}}'},
        {"name": "Ink 2", "comment": '{"swatch2025": {"theme": "Year End", "date": "2025-12-31"}}'},
        {"name": "Ink 3", "comment": ""},
    ]

    assignments = create_yearly_assignments_with_inks(inks, 2025, seed=42)

    # Ink 0 should be assigned to Jan 1
    assert assignments.get("2025-01-01") == 0

    # Ink 1 should be assigned to Dec 31
    assert assignments.get("2025-12-31") == 1

    # Ink 2 should be randomly assigned somewhere
    assert 2 in assignments.values()

    # All assignments should be unique
    assert validate_assignments_unique(assignments)


def test_create_yearly_assignments_with_inks_no_explicit_dates():
    """Test that without explicit dates, behavior is like random assignment"""
    inks = [
        {"name": "Ink 1", "comment": ""},
        {"name": "Ink 2", "comment": ""},
        {"name": "Ink 3", "comment": ""},
    ]

    assignments = create_yearly_assignments_with_inks(inks, 2025, seed=42)

    # Should have 3 assignments
    assert len(assignments) == 3

    # All should be unique
    assert validate_assignments_unique(assignments)


def test_create_yearly_assignments_with_inks_duplicate_date():
    """Test that if two inks claim same date, only first gets it"""
    inks = [
        {"name": "Ink 1", "comment": '{"swatch2025": {"date": "2025-06-15"}}'},
        {"name": "Ink 2", "comment": '{"swatch2025": {"date": "2025-06-15"}}'},  # Duplicate!
        {"name": "Ink 3", "comment": ""},
    ]

    assignments = create_yearly_assignments_with_inks(inks, 2025, seed=42)

    # Only ink 0 should get June 15
    assert assignments.get("2025-06-15") == 0

    # Ink 1 should be assigned somewhere else
    assert 1 in assignments.values()
    # But not to June 15
    assert assignments.get("2025-06-15") != 1

    # All assignments should be unique
    assert validate_assignments_unique(assignments)


def test_create_yearly_assignments_with_inks_old_format_backward_compat():
    """Test backward compatibility with old format"""
    inks = [
        {"name": "Ink 1", "comment": '{"swatch2025": "2025-01-01"}'},  # Old format
        {"name": "Ink 2", "comment": ""},
    ]

    assignments = create_yearly_assignments_with_inks(inks, 2025, seed=42)

    # Old format should still work
    assert assignments.get("2025-01-01") == 0
    assert validate_assignments_unique(assignments)


def test_create_yearly_assignments_with_inks_empty_list():
    """Test with empty ink list"""
    assignments = create_yearly_assignments_with_inks([], 2025)

    assert assignments == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
