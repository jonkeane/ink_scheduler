"""
Tests for ink assignment logic
"""
import pytest
import json
from assignment_logic import (
    parse_swatch_date_from_comment,
    get_month_summary,
    parse_comment_json,
    has_assignment,
    find_ink_by_name,
    search_inks,
    get_swatch_data,
    parse_theme_from_comment,
    create_explicit_assignments_only,
    move_ink_assignment,
    swap_ink_assignments,
    MoveResult,
    check_overwrite_conflict,
    build_swatch_comment_json,
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


# =============================================================================
# Tests for get_swatch_data
# =============================================================================

def test_get_swatch_data_valid():
    """Test getting valid swatch data dict"""
    comment = '{"swatch2026": {"date": "2026-01-15", "theme": "Test"}}'
    result = get_swatch_data(comment, 2026)
    assert result == {"date": "2026-01-15", "theme": "Test"}


def test_get_swatch_data_not_a_dict():
    """Test swatch key exists but value is not a dict"""
    comment = '{"swatch2026": "2026-01-15"}'
    result = get_swatch_data(comment, 2026)
    assert result is None


def test_get_swatch_data_missing_key():
    """Test missing swatch key"""
    comment = '{"other": "value"}'
    result = get_swatch_data(comment, 2026)
    assert result is None


def test_get_swatch_data_invalid_json():
    """Test invalid JSON comment"""
    result = get_swatch_data("not json", 2026)
    assert result is None


# =============================================================================
# Tests for parse_theme_from_comment
# =============================================================================

def test_parse_theme_from_comment_both_fields():
    """Test parsing theme with both theme and theme_description"""
    comment = '{"swatch2026": {"theme": "Winter", "theme_description": "Cold inks"}}'
    result = parse_theme_from_comment(comment, 2026)
    assert result == {"theme": "Winter", "theme_description": "Cold inks"}


def test_parse_theme_from_comment_only_theme():
    """Test parsing with only theme field"""
    comment = '{"swatch2026": {"theme": "Winter"}}'
    result = parse_theme_from_comment(comment, 2026)
    assert result == {"theme": "Winter", "theme_description": ""}


def test_parse_theme_from_comment_only_description():
    """Test parsing with only theme_description field"""
    comment = '{"swatch2026": {"theme_description": "Cold inks"}}'
    result = parse_theme_from_comment(comment, 2026)
    assert result == {"theme": "", "theme_description": "Cold inks"}


def test_parse_theme_from_comment_no_swatch_data():
    """Test parsing with no swatch data for year"""
    comment = '{"swatch2025": {"theme": "Winter"}}'
    result = parse_theme_from_comment(comment, 2026)
    assert result is None


def test_parse_theme_from_comment_no_theme_fields():
    """Test parsing with swatch data but no theme fields"""
    comment = '{"swatch2026": {"date": "2026-01-15"}}'
    result = parse_theme_from_comment(comment, 2026)
    assert result is None


# =============================================================================
# Tests for create_explicit_assignments_only
# =============================================================================

def test_create_explicit_assignments_empty_list():
    """Test with empty ink list"""
    result = create_explicit_assignments_only([], 2026)
    assert result == {}


def test_create_explicit_assignments_single_ink():
    """Test with single ink with valid assignment"""
    inks = [
        {"private_comment": '{"swatch2026": {"date": "2026-01-15"}}'}
    ]
    result = create_explicit_assignments_only(inks, 2026)
    assert result == {"2026-01-15": 0}


def test_create_explicit_assignments_multiple_inks():
    """Test with multiple inks with assignments"""
    inks = [
        {"private_comment": '{"swatch2026": {"date": "2026-01-15"}}'},
        {"private_comment": '{"swatch2026": {"date": "2026-01-20"}}'},
        {"private_comment": '{"swatch2026": {"date": "2026-02-01"}}'},
    ]
    result = create_explicit_assignments_only(inks, 2026)
    assert result == {"2026-01-15": 0, "2026-01-20": 1, "2026-02-01": 2}


def test_create_explicit_assignments_duplicate_dates():
    """Test duplicate date assignments - first wins"""
    inks = [
        {"private_comment": '{"swatch2026": {"date": "2026-01-15"}}'},
        {"private_comment": '{"swatch2026": {"date": "2026-01-15"}}'},  # duplicate
    ]
    result = create_explicit_assignments_only(inks, 2026)
    assert result == {"2026-01-15": 0}  # first ink wins


def test_create_explicit_assignments_mixed():
    """Test inks with and without assignments"""
    inks = [
        {"private_comment": '{"swatch2026": {"date": "2026-01-15"}}'},
        {"private_comment": ""},  # no assignment
        {"private_comment": '{"swatch2026": {"date": "2026-01-20"}}'},
    ]
    result = create_explicit_assignments_only(inks, 2026)
    assert result == {"2026-01-15": 0, "2026-01-20": 2}


# =============================================================================
# Tests for MoveResult
# =============================================================================

def test_move_result_success():
    """Test MoveResult success case"""
    result = MoveResult(True, "Assignment successful", operation="assign")
    assert result.success is True
    assert result.message == "Assignment successful"
    assert result.data == {"operation": "assign"}


def test_move_result_failure():
    """Test MoveResult failure case"""
    result = MoveResult(False, "Date is protected", protected=True)
    assert result.success is False
    assert result.message == "Date is protected"
    assert result.data == {"protected": True}


def test_move_result_to_dict():
    """Test MoveResult to_dict method"""
    result = MoveResult(True, "Done", operation="move", from_date="2026-01-15")
    d = result.to_dict()
    assert d == {
        "success": True,
        "message": "Done",
        "operation": "move",
        "from_date": "2026-01-15"
    }


# =============================================================================
# Tests for move_ink_assignment
# =============================================================================

class TestMoveInkAssignmentValidation:
    """Tests for move_ink_assignment validation errors"""

    def test_no_dates_provided(self):
        """Test error when neither from_date nor to_date provided"""
        session = {}
        api = {}
        new_session, result = move_ink_assignment(session, api, None, None)
        assert result.success is False
        assert "Must specify" in result.message
        assert new_session == session

    def test_invalid_from_date_format(self):
        """Test error for invalid from_date format"""
        session = {"bad-date": 0}
        api = {}
        new_session, result = move_ink_assignment(session, api, "bad-date", None)
        assert result.success is False
        assert "Invalid from_date format" in result.message

    def test_invalid_to_date_format(self):
        """Test error for invalid to_date format"""
        session = {}
        api = {}
        new_session, result = move_ink_assignment(session, api, None, "bad-date", ink_idx=0)
        assert result.success is False
        assert "Invalid to_date format" in result.message


class TestMoveInkAssignmentAssign:
    """Tests for move_ink_assignment assign operation (from_date=None)"""

    def test_assign_success(self):
        """Test successful assign to empty date"""
        session = {}
        api = {}
        new_session, result = move_ink_assignment(session, api, None, "2026-01-15", ink_idx=0)
        assert result.success is True
        assert new_session == {"2026-01-15": 0}
        assert result.data["operation"] == "assign"

    def test_assign_to_api_protected_date(self):
        """Test assign fails when to_date is API-protected"""
        session = {}
        api = {"2026-01-15": 5}
        new_session, result = move_ink_assignment(session, api, None, "2026-01-15", ink_idx=0)
        assert result.success is False
        assert "protected" in result.message.lower()
        assert new_session == session

    def test_assign_ink_already_assigned(self):
        """Test assign fails when ink is already assigned elsewhere"""
        session = {"2026-01-10": 0}
        api = {}
        new_session, result = move_ink_assignment(session, api, None, "2026-01-15", ink_idx=0)
        assert result.success is False
        assert "already assigned" in result.message.lower()
        assert result.data.get("assigned_date") == "2026-01-10"

    def test_assign_with_displacement(self):
        """Test assign overwrites existing session assignment"""
        session = {"2026-01-15": 5}  # existing assignment
        api = {}
        new_session, result = move_ink_assignment(session, api, None, "2026-01-15", ink_idx=0)
        assert result.success is True
        assert new_session == {"2026-01-15": 0}
        assert result.data.get("displaced_ink_idx") == 5

    def test_assign_without_ink_idx(self):
        """Test assign fails without ink_idx"""
        session = {}
        api = {}
        new_session, result = move_ink_assignment(session, api, None, "2026-01-15")
        assert result.success is False
        assert "ink_idx is required" in result.message

    def test_assign_with_ink_info(self):
        """Test assign includes ink info when inks provided"""
        session = {}
        api = {}
        inks = [{"brand_name": "Diamine", "name": "Blue Velvet"}]
        new_session, result = move_ink_assignment(session, api, None, "2026-01-15", ink_idx=0, inks=inks)
        assert result.success is True
        assert result.data.get("ink_brand") == "Diamine"
        assert result.data.get("ink_name") == "Blue Velvet"


class TestMoveInkAssignmentUnassign:
    """Tests for move_ink_assignment unassign operation (to_date=None)"""

    def test_unassign_success(self):
        """Test successful unassign from session date"""
        session = {"2026-01-15": 0}
        api = {}
        new_session, result = move_ink_assignment(session, api, "2026-01-15", None)
        assert result.success is True
        assert new_session == {}
        assert result.data["operation"] == "unassign"

    def test_unassign_api_protected(self):
        """Test unassign fails when from_date is API-protected"""
        session = {}
        api = {"2026-01-15": 0}
        new_session, result = move_ink_assignment(session, api, "2026-01-15", None)
        assert result.success is False
        assert "protected" in result.message.lower()

    def test_unassign_no_session_assignment(self):
        """Test unassign fails when from_date has no session assignment"""
        session = {}
        api = {}
        new_session, result = move_ink_assignment(session, api, "2026-01-15", None)
        assert result.success is False
        assert "No session assignment" in result.message

    def test_unassign_ink_idx_mismatch(self):
        """Test unassign fails with ink index mismatch"""
        session = {"2026-01-15": 0}
        api = {}
        new_session, result = move_ink_assignment(session, api, "2026-01-15", None, ink_idx=5)
        assert result.success is False
        assert "mismatch" in result.message.lower()


class TestMoveInkAssignmentMove:
    """Tests for move_ink_assignment move operation (both dates set)"""

    def test_move_success(self):
        """Test successful move from one date to another"""
        session = {"2026-01-15": 0}
        api = {}
        new_session, result = move_ink_assignment(session, api, "2026-01-15", "2026-01-20")
        assert result.success is True
        assert new_session == {"2026-01-20": 0}
        assert result.data["operation"] == "move"
        assert result.data["from_date"] == "2026-01-15"
        assert result.data["to_date"] == "2026-01-20"

    def test_move_from_api_protected(self):
        """Test move fails when from_date is API-protected"""
        session = {}
        api = {"2026-01-15": 0}
        new_session, result = move_ink_assignment(session, api, "2026-01-15", "2026-01-20")
        assert result.success is False
        assert "protected" in result.message.lower()

    def test_move_to_api_protected(self):
        """Test move fails when to_date is API-protected"""
        session = {"2026-01-15": 0}
        api = {"2026-01-20": 5}
        new_session, result = move_ink_assignment(session, api, "2026-01-15", "2026-01-20")
        assert result.success is False
        assert "protected" in result.message.lower()

    def test_move_with_displacement(self):
        """Test move with displacement at target date"""
        session = {"2026-01-15": 0, "2026-01-20": 5}
        api = {}
        new_session, result = move_ink_assignment(session, api, "2026-01-15", "2026-01-20")
        assert result.success is True
        assert new_session == {"2026-01-20": 0}  # ink 0 moved, ink 5 displaced
        assert result.data.get("displaced_ink_idx") == 5


class TestCheckOverwriteConflict:
    """Tests for check_overwrite_conflict function"""

    def test_no_conflict_empty_comment(self):
        """Test no conflict when ink has no private_comment"""
        ink = {"private_comment": ""}
        result = check_overwrite_conflict(ink, 2026)
        assert result is None

    def test_no_conflict_no_swatch_data(self):
        """Test no conflict when ink has comment but no swatch data"""
        ink = {"private_comment": '{"notes": "Great ink!"}'}
        result = check_overwrite_conflict(ink, 2026)
        assert result is None

    def test_no_conflict_different_year(self):
        """Test no conflict when ink has swatch data for different year"""
        ink = {"private_comment": '{"swatch2025": {"date": "2025-05-15"}}'}
        result = check_overwrite_conflict(ink, 2026)
        assert result is None

    def test_conflict_detected(self):
        """Test conflict detected when ink has swatch data for same year"""
        ink = {"private_comment": '{"swatch2026": {"date": "2026-01-15", "theme": "Winter"}}'}
        result = check_overwrite_conflict(ink, 2026)
        assert result is not None
        assert result["existing_date"] == "2026-01-15"
        assert result["existing_theme"] == "Winter"

    def test_conflict_no_theme(self):
        """Test conflict detected returns None for missing theme"""
        ink = {"private_comment": '{"swatch2026": {"date": "2026-01-15"}}'}
        result = check_overwrite_conflict(ink, 2026)
        assert result is not None
        assert result["existing_date"] == "2026-01-15"
        assert result["existing_theme"] is None


class TestBuildSwatchCommentJson:
    """Tests for build_swatch_comment_json function"""

    def test_build_from_empty(self):
        """Test building swatch JSON from empty comment"""
        result = build_swatch_comment_json("", 2026, "2026-01-15")
        data = json.loads(result)
        assert data["swatch2026"]["date"] == "2026-01-15"
        assert "theme" not in data["swatch2026"]

    def test_build_with_theme(self):
        """Test building swatch JSON with theme"""
        result = build_swatch_comment_json("", 2026, "2026-01-15", "Winter Blues", "Cool tones")
        data = json.loads(result)
        assert data["swatch2026"]["date"] == "2026-01-15"
        assert data["swatch2026"]["theme"] == "Winter Blues"
        assert data["swatch2026"]["theme_description"] == "Cool tones"

    def test_preserve_other_years(self):
        """Test that other years' swatch data is preserved"""
        existing = '{"swatch2025": {"date": "2025-05-15", "theme": "Spring"}}'
        result = build_swatch_comment_json(existing, 2026, "2026-01-15")
        data = json.loads(result)
        # New year added
        assert data["swatch2026"]["date"] == "2026-01-15"
        # Old year preserved
        assert data["swatch2025"]["date"] == "2025-05-15"
        assert data["swatch2025"]["theme"] == "Spring"

    def test_preserve_other_fields(self):
        """Test that non-swatch fields are preserved"""
        existing = '{"notes": "Great ink!", "rating": 5}'
        result = build_swatch_comment_json(existing, 2026, "2026-01-15")
        data = json.loads(result)
        assert data["swatch2026"]["date"] == "2026-01-15"
        assert data["notes"] == "Great ink!"
        assert data["rating"] == 5

    def test_overwrite_same_year(self):
        """Test that same year swatch data is overwritten"""
        existing = '{"swatch2026": {"date": "2026-01-01", "theme": "Old Theme"}}'
        result = build_swatch_comment_json(existing, 2026, "2026-02-15", "New Theme")
        data = json.loads(result)
        assert data["swatch2026"]["date"] == "2026-02-15"
        assert data["swatch2026"]["theme"] == "New Theme"

    def test_invalid_existing_json(self):
        """Test handling of invalid existing JSON"""
        result = build_swatch_comment_json("not valid json", 2026, "2026-01-15")
        data = json.loads(result)
        assert data["swatch2026"]["date"] == "2026-01-15"

    def test_none_existing_comment(self):
        """Test handling of None existing comment"""
        result = build_swatch_comment_json(None, 2026, "2026-01-15")
        data = json.loads(result)
        assert data["swatch2026"]["date"] == "2026-01-15"


# =============================================================================
# Tests for swap_ink_assignments
# =============================================================================

class TestSwapInkAssignments:
    """Tests for swap_ink_assignments function (drag-and-drop swap)"""

    def test_swap_success(self):
        """Test successful swap between two session assignments"""
        session = {"2026-01-15": 0, "2026-01-20": 1}
        api = {}
        new_session, result = swap_ink_assignments(session, api, "2026-01-15", "2026-01-20")
        assert result.success is True
        assert new_session == {"2026-01-15": 1, "2026-01-20": 0}
        assert result.data["operation"] == "swap"

    def test_swap_invalid_date1_format(self):
        """Test swap fails with invalid date1 format"""
        session = {"bad-date": 0, "2026-01-20": 1}
        api = {}
        new_session, result = swap_ink_assignments(session, api, "bad-date", "2026-01-20")
        assert result.success is False
        assert "Invalid date1 format" in result.message
        assert new_session == session

    def test_swap_invalid_date2_format(self):
        """Test swap fails with invalid date2 format"""
        session = {"2026-01-15": 0, "bad-date": 1}
        api = {}
        new_session, result = swap_ink_assignments(session, api, "2026-01-15", "bad-date")
        assert result.success is False
        assert "Invalid date2 format" in result.message
        assert new_session == session

    def test_swap_date1_api_protected(self):
        """Test swap fails when date1 is API-protected"""
        session = {"2026-01-20": 1}
        api = {"2026-01-15": 0}
        new_session, result = swap_ink_assignments(session, api, "2026-01-15", "2026-01-20")
        assert result.success is False
        assert "protected" in result.message.lower()
        assert result.data.get("protected") is True

    def test_swap_date2_api_protected(self):
        """Test swap fails when date2 is API-protected"""
        session = {"2026-01-15": 0}
        api = {"2026-01-20": 1}
        new_session, result = swap_ink_assignments(session, api, "2026-01-15", "2026-01-20")
        assert result.success is False
        assert "protected" in result.message.lower()
        assert result.data.get("protected") is True

    def test_swap_date1_no_assignment(self):
        """Test swap fails when date1 has no assignment"""
        session = {"2026-01-20": 1}
        api = {}
        new_session, result = swap_ink_assignments(session, api, "2026-01-15", "2026-01-20")
        assert result.success is False
        assert "No assignment found for 2026-01-15" in result.message

    def test_swap_date2_no_assignment(self):
        """Test swap fails when date2 has no assignment"""
        session = {"2026-01-15": 0}
        api = {}
        new_session, result = swap_ink_assignments(session, api, "2026-01-15", "2026-01-20")
        assert result.success is False
        assert "No assignment found for 2026-01-20" in result.message

    def test_swap_with_ink_info(self):
        """Test swap includes ink info when inks provided"""
        session = {"2026-01-15": 0, "2026-01-20": 1}
        api = {}
        inks = [
            {"brand_name": "Diamine", "name": "Blue Velvet"},
            {"brand_name": "Pilot", "name": "Iroshizuku"}
        ]
        new_session, result = swap_ink_assignments(session, api, "2026-01-15", "2026-01-20", inks=inks)
        assert result.success is True
        assert result.data.get("ink1_brand") == "Diamine"
        assert result.data.get("ink1_name") == "Blue Velvet"
        assert result.data.get("ink2_brand") == "Pilot"
        assert result.data.get("ink2_name") == "Iroshizuku"

    def test_swap_preserves_other_assignments(self):
        """Test swap doesn't affect other assignments"""
        session = {"2026-01-15": 0, "2026-01-20": 1, "2026-01-25": 2}
        api = {}
        new_session, result = swap_ink_assignments(session, api, "2026-01-15", "2026-01-20")
        assert result.success is True
        assert new_session["2026-01-25"] == 2  # unchanged
        assert new_session["2026-01-15"] == 1  # swapped
        assert new_session["2026-01-20"] == 0  # swapped

    def test_swap_does_not_mutate_original(self):
        """Test swap returns new dict and doesn't mutate original"""
        session = {"2026-01-15": 0, "2026-01-20": 1}
        api = {}
        original_session = session.copy()
        new_session, result = swap_ink_assignments(session, api, "2026-01-15", "2026-01-20")
        assert result.success is True
        assert session == original_session  # original unchanged
        assert new_session is not session  # new dict returned


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
