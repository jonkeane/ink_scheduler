"""
Comprehensive tests for chat_tools.py - Tool functions for LLM chat.

These tests verify the 12 tool functions that interact with ink assignments
through reactive state management.
"""
import pytest
from conftest import MockReactive
from chat_tools import create_tool_functions


# =============================================================================
# Helper to create tool functions with mock state
# =============================================================================

def setup_tools(inks=None, year=2026, session=None, api=None, themes=None):
    """
    Set up tool functions with mock reactive state.

    Returns tuple of (tools_dict, update_snapshot) where tools_dict
    maps function names to the actual functions.
    """
    ink_data = MockReactive(inks or [])
    selected_year = MockReactive(year)
    session_assignments = MockReactive(session or {})
    api_assignments = MockReactive(api or {})
    session_themes = MockReactive(themes or {})

    tools_list, update_snapshot = create_tool_functions(
        ink_data, selected_year, session_assignments, api_assignments, session_themes
    )

    # Convert list to dict for easier access
    tools = {func.__name__: func for func in tools_list}

    # Initialize snapshot
    update_snapshot()

    return tools, update_snapshot, session_assignments, session_themes


# =============================================================================
# Tests for list_all_inks()
# =============================================================================

class TestListAllInks:
    """Tests for list_all_inks tool function."""

    def test_empty_collection(self):
        """Test with no inks in collection."""
        tools, _, _, _ = setup_tools(inks=[])
        result = tools["list_all_inks"]()

        assert result["success"] is False
        assert "No inks available" in result["message"]

    def test_with_inks_no_assignments(self, sample_inks):
        """Test with inks but no assignments."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["list_all_inks"]()

        assert result["success"] is True
        assert result["total_inks"] == 5
        assert len(result["inks"]) == 5
        # All should be unassigned
        for ink in result["inks"]:
            assert ink["already_assigned"] is False

    def test_with_assigned_inks(self, sample_inks):
        """Test that assigned inks are marked correctly."""
        tools, _, _, _ = setup_tools(
            inks=sample_inks,
            session={"2026-01-01": 0, "2026-01-02": 1}
        )
        result = tools["list_all_inks"]()

        assert result["success"] is True
        # Ink 0 and 1 should be assigned
        ink_0 = next(i for i in result["inks"] if i["index"] == 0)
        ink_1 = next(i for i in result["inks"] if i["index"] == 1)
        ink_2 = next(i for i in result["inks"] if i["index"] == 2)

        assert ink_0["already_assigned"] is True
        assert ink_1["already_assigned"] is True
        assert ink_2["already_assigned"] is False

    def test_merged_view(self, sample_inks):
        """Test that API and session assignments are merged."""
        tools, _, _, _ = setup_tools(
            inks=sample_inks,
            session={"2026-01-01": 0},
            api={"2026-01-02": 1}
        )
        result = tools["list_all_inks"]()

        ink_0 = next(i for i in result["inks"] if i["index"] == 0)
        ink_1 = next(i for i in result["inks"] if i["index"] == 1)

        assert ink_0["already_assigned"] is True  # Session
        assert ink_1["already_assigned"] is True  # API


# =============================================================================
# Tests for search_inks()
# =============================================================================

class TestSearchInks:
    """Tests for search_inks tool function."""

    def test_query_filter_name(self, sample_inks):
        """Test searching by ink name."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["search_inks"](query="Velvet")

        assert result["success"] is True
        assert result["matches_found"] == 1
        assert result["matches"][0]["name"] == "Blue Velvet"

    def test_query_filter_brand(self, sample_inks):
        """Test searching by brand name."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["search_inks"](query="Diamine")

        assert result["success"] is True
        assert result["matches_found"] == 2  # Blue Velvet and Oxblood

    def test_color_filter(self, sample_inks):
        """Test filtering by color tag."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["search_inks"](color="blue")

        assert result["success"] is True
        assert result["matches_found"] == 2  # Blue Velvet and Kon-peki

    def test_brand_filter(self, sample_inks):
        """Test filtering by brand."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["search_inks"](brand="Pilot")

        assert result["success"] is True
        assert result["matches_found"] == 1
        assert result["matches"][0]["brand"] == "Pilot"

    def test_no_matches(self, sample_inks):
        """Test search with no matches."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["search_inks"](query="NonexistentInk")

        assert result["success"] is True
        assert result["matches_found"] == 0

    def test_case_insensitivity(self, sample_inks):
        """Test that search is case insensitive."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["search_inks"](query="VELVET")

        assert result["success"] is True
        assert result["matches_found"] == 1


# =============================================================================
# Tests for get_month_assignments()
# =============================================================================

class TestGetMonthAssignments:
    """Tests for get_month_assignments tool function."""

    def test_invalid_month_zero(self, sample_inks):
        """Test with invalid month 0."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["get_month_assignments"](month=0)

        assert result["success"] is False
        assert "Invalid month" in result["message"]

    def test_invalid_month_13(self, sample_inks):
        """Test with invalid month 13."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["get_month_assignments"](month=13)

        assert result["success"] is False
        assert "Invalid month" in result["message"]

    def test_valid_month_no_assignments(self, sample_inks):
        """Test valid month with no assignments."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["get_month_assignments"](month=3)

        assert result["success"] is True
        assert result["month"] == 3
        assert result["month_name"] == "March"
        assert result["assigned_days"] == 0
        assert result["days_in_month"] == 31

    def test_api_assignments_protected(self, sample_inks):
        """Test that API assignments are marked as protected."""
        tools, _, _, _ = setup_tools(
            inks=sample_inks,
            api={"2026-01-15": 1}
        )
        result = tools["get_month_assignments"](month=1)

        assert result["success"] is True
        assert len(result["assignments"]) == 1
        assert result["assignments"][0]["protected"] is True

    def test_session_assignments_not_protected(self, sample_inks):
        """Test that session assignments are not protected."""
        tools, _, _, _ = setup_tools(
            inks=sample_inks,
            session={"2026-01-15": 1}
        )
        result = tools["get_month_assignments"](month=1)

        assert result["success"] is True
        assert len(result["assignments"]) == 1
        assert result["assignments"][0]["protected"] is False

    def test_leap_year_february(self, sample_inks):
        """Test February in a leap year (2024)."""
        tools, _, _, _ = setup_tools(inks=sample_inks, year=2024)
        result = tools["get_month_assignments"](month=2, year=2024)

        assert result["success"] is True
        assert result["days_in_month"] == 29


# =============================================================================
# Tests for assign_ink_to_date()
# =============================================================================

class TestAssignInkToDate:
    """Tests for assign_ink_to_date tool function."""

    def test_successful_assignment(self, sample_inks):
        """Test successful new assignment."""
        tools, _, session_reactive, _ = setup_tools(inks=sample_inks)
        result = tools["assign_ink_to_date"](
            ink_identifier="Blue Velvet",
            date_str="2026-01-01"
        )

        assert result["success"] is True
        assert result["ink_index"] == 0
        assert result["date"] == "2026-01-01"
        # Verify reactive state was updated
        assert session_reactive.get()["2026-01-01"] == 0

    def test_api_protected_date(self, sample_inks):
        """Test that API-protected dates cannot be assigned."""
        tools, _, _, _ = setup_tools(
            inks=sample_inks,
            api={"2026-01-15": 1}
        )
        result = tools["assign_ink_to_date"](
            ink_identifier="Blue Velvet",
            date_str="2026-01-15"
        )

        assert result["success"] is False

    def test_ink_already_assigned(self, sample_inks):
        """Test that inks already assigned elsewhere fail."""
        tools, _, _, _ = setup_tools(
            inks=sample_inks,
            session={"2026-01-01": 0}  # Ink 0 already assigned
        )
        result = tools["assign_ink_to_date"](
            ink_identifier="Blue Velvet",
            date_str="2026-01-15"
        )

        assert result["success"] is False

    def test_ink_not_found(self, sample_inks):
        """Test with ink that doesn't exist."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["assign_ink_to_date"](
            ink_identifier="Nonexistent Ink",
            date_str="2026-01-01"
        )

        assert result["success"] is False
        assert "Could not find ink" in result["message"]

    def test_displacing_session_assignment(self, sample_inks):
        """Test that session assignments can be displaced."""
        tools, _, session_reactive, _ = setup_tools(
            inks=sample_inks,
            session={"2026-01-01": 1}  # Ink 1 on Jan 1
        )
        result = tools["assign_ink_to_date"](
            ink_identifier="Blue Velvet",  # Ink 0
            date_str="2026-01-01"
        )

        assert result["success"] is True
        assert session_reactive.get()["2026-01-01"] == 0

    def test_fuzzy_ink_matching(self, sample_inks):
        """Test fuzzy matching by brand + name."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["assign_ink_to_date"](
            ink_identifier="Diamine Blue Velvet",
            date_str="2026-01-01"
        )

        assert result["success"] is True
        assert result["ink_index"] == 0

    def test_no_inks_available(self):
        """Test with empty ink collection."""
        tools, _, _, _ = setup_tools(inks=[])
        result = tools["assign_ink_to_date"](
            ink_identifier="Any Ink",
            date_str="2026-01-01"
        )

        assert result["success"] is False
        assert "No inks available" in result["message"]


# =============================================================================
# Tests for bulk_assign_month()
# =============================================================================

class TestBulkAssignMonth:
    """Tests for bulk_assign_month tool function."""

    def test_invalid_month(self, sample_inks):
        """Test with invalid month."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["bulk_assign_month"](
            ink_identifiers=["Blue Velvet"],
            month=13
        )

        assert result["success"] is False
        assert "Invalid month" in result["message"]

    def test_successful_bulk_assignment(self, sample_inks):
        """Test successful bulk assignment."""
        tools, _, session_reactive, _ = setup_tools(inks=sample_inks)
        result = tools["bulk_assign_month"](
            ink_identifiers=["Blue Velvet", "Apache Sunset"],
            month=1
        )

        assert result["success"] is True
        assert result["successful_assignments"] == 2
        assert len(result["successful"]) == 2
        # Verify assignments were made
        session = session_reactive.get()
        assert len(session) == 2

    def test_more_inks_than_days(self, sample_inks):
        """Test when more inks requested than available days."""
        # Create 35 inks (more than any month has days)
        many_inks = [{"id": str(i), "brand_name": "Test", "name": f"Ink{i}"} for i in range(35)]
        tools, _, _, _ = setup_tools(inks=many_inks)
        result = tools["bulk_assign_month"](
            ink_identifiers=[f"Ink{i}" for i in range(35)],
            month=2  # February has 28 days
        )

        assert result["success"] is False
        assert "Not enough days" in result["message"]

    def test_some_inks_already_assigned(self, sample_inks):
        """Test when some inks are already assigned."""
        tools, _, _, _ = setup_tools(
            inks=sample_inks,
            session={"2026-02-14": 0}  # Ink 0 already assigned
        )
        result = tools["bulk_assign_month"](
            ink_identifiers=["Blue Velvet", "Apache Sunset"],  # Ink 0 and 2
            month=1
        )

        assert result["successful_assignments"] == 1  # Only Apache Sunset
        assert result["already_assigned_inks"] == 1

    def test_ink_not_found_partial_failure(self, sample_inks):
        """Test partial failure when some inks not found."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["bulk_assign_month"](
            ink_identifiers=["Blue Velvet", "Nonexistent Ink"],
            month=1
        )

        assert result["successful_assignments"] == 1
        assert result["failed_assignments"] == 1
        assert "Ink not found" in result["failed"][0]["reason"]

    def test_protected_dates_preserved(self, sample_inks):
        """Test that API-protected dates are skipped."""
        # Fill some January dates with API assignments (only using inks 0 and 1)
        api = {"2026-01-01": 0, "2026-01-02": 1, "2026-01-03": 0}
        tools, _, session_reactive, _ = setup_tools(inks=sample_inks, api=api)
        result = tools["bulk_assign_month"](
            ink_identifiers=["Yama-dori"],  # Ink 3, not assigned via API
            month=1
        )

        # Should succeed - assigns to first available day (day 4 since 1-3 are taken)
        assert result["success"] is True
        assert result["successful_assignments"] == 1
        # Should have assigned to a day not occupied by API
        session = session_reactive.get()
        assert "2026-01-04" in session  # First available day

    def test_empty_ink_list(self, sample_inks):
        """Test with empty ink identifiers list."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["bulk_assign_month"](
            ink_identifiers=[],
            month=1
        )

        assert result["success"] is False
        assert result["successful_assignments"] == 0

    def test_return_structure(self, sample_inks):
        """Test that return structure has all expected fields."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["bulk_assign_month"](
            ink_identifiers=["Blue Velvet"],
            month=1
        )

        assert "month" in result
        assert "month_name" in result
        assert "year" in result
        assert "successful_assignments" in result
        assert "failed_assignments" in result
        assert "already_assigned_inks" in result
        assert "successful" in result
        assert "failed" in result
        assert "already_assigned" in result


# =============================================================================
# Tests for unassign_ink_from_date()
# =============================================================================

class TestUnassignInkFromDate:
    """Tests for unassign_ink_from_date tool function."""

    def test_successful_unassignment(self, sample_inks):
        """Test successful unassignment."""
        tools, _, session_reactive, _ = setup_tools(
            inks=sample_inks,
            session={"2026-01-01": 0}
        )
        result = tools["unassign_ink_from_date"](date_str="2026-01-01")

        assert result["success"] is True
        assert "2026-01-01" not in session_reactive.get()

    def test_api_protected_date(self, sample_inks):
        """Test that API-protected dates cannot be unassigned."""
        tools, _, _, _ = setup_tools(
            inks=sample_inks,
            api={"2026-01-15": 1}
        )
        result = tools["unassign_ink_from_date"](date_str="2026-01-15")

        assert result["success"] is False

    def test_no_session_assignment(self, sample_inks):
        """Test unassigning date with no session assignment."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["unassign_ink_from_date"](date_str="2026-01-01")

        assert result["success"] is False

    def test_reactive_state_update(self, sample_inks):
        """Test that reactive state is properly updated."""
        tools, _, session_reactive, _ = setup_tools(
            inks=sample_inks,
            session={"2026-01-01": 0, "2026-01-02": 1}
        )
        tools["unassign_ink_from_date"](date_str="2026-01-01")

        session = session_reactive.get()
        assert "2026-01-01" not in session
        assert "2026-01-02" in session  # Other assignment preserved


# =============================================================================
# Tests for clear_month_assignments()
# =============================================================================

class TestClearMonthAssignments:
    """Tests for clear_month_assignments tool function."""

    def test_invalid_month(self, sample_inks):
        """Test with invalid month."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["clear_month_assignments"](month=0)

        assert result["success"] is False
        assert "Invalid month" in result["message"]

    def test_empty_month(self, sample_inks):
        """Test clearing month with no assignments."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["clear_month_assignments"](month=1)

        assert result["success"] is True
        assert result["removed_count"] == 0

    def test_session_assignments_only(self, sample_inks):
        """Test clearing only session assignments."""
        tools, _, session_reactive, _ = setup_tools(
            inks=sample_inks,
            session={"2026-01-01": 0, "2026-01-15": 1, "2026-02-01": 2}
        )
        result = tools["clear_month_assignments"](month=1)

        assert result["success"] is True
        assert result["removed_count"] == 2
        # February assignment should remain
        assert "2026-02-01" in session_reactive.get()

    def test_preserves_api_assignments(self, sample_inks):
        """Test that API assignments are preserved."""
        tools, _, session_reactive, _ = setup_tools(
            inks=sample_inks,
            session={"2026-01-01": 0},
            api={"2026-01-15": 1}
        )
        result = tools["clear_month_assignments"](month=1)

        assert result["removed_count"] == 1  # Only session assignment
        assert result["protected_count"] == 1  # API assignment protected

    def test_return_counts(self, sample_inks):
        """Test that removed and protected counts are correct."""
        tools, _, _, _ = setup_tools(
            inks=sample_inks,
            session={"2026-03-01": 0, "2026-03-15": 2},
            api={"2026-03-10": 1}
        )
        result = tools["clear_month_assignments"](month=3)

        assert result["removed_count"] == 2
        assert result["protected_count"] == 1


# =============================================================================
# Tests for get_current_assignments_summary()
# =============================================================================

class TestGetCurrentAssignmentsSummary:
    """Tests for get_current_assignments_summary tool function."""

    def test_empty_assignments(self, sample_inks):
        """Test with no assignments."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["get_current_assignments_summary"]()

        assert result["success"] is True
        assert result["total_assigned_days"] == 0
        assert result["total_days_in_year"] == 365  # 2026 is not a leap year

    def test_multiple_months(self, sample_inks):
        """Test with assignments across multiple months."""
        tools, _, _, _ = setup_tools(
            inks=sample_inks,
            session={"2026-01-01": 0, "2026-02-14": 1, "2026-03-01": 2}
        )
        result = tools["get_current_assignments_summary"]()

        assert result["success"] is True
        assert result["total_assigned_days"] == 3

    def test_api_vs_session_counts(self, sample_inks):
        """Test that API and session counts are separate."""
        tools, _, _, _ = setup_tools(
            inks=sample_inks,
            session={"2026-01-01": 0},
            api={"2026-01-15": 1}
        )
        result = tools["get_current_assignments_summary"]()

        jan = next(m for m in result["monthly_summary"] if m["month"] == 1)
        assert jan["api_assignments"] == 1
        assert jan["session_assignments"] == 1
        assert jan["assigned_days"] == 2

    def test_leap_year(self, sample_inks):
        """Test leap year has correct total days."""
        tools, _, _, _ = setup_tools(inks=sample_inks, year=2024)
        result = tools["get_current_assignments_summary"](year=2024)

        assert result["total_days_in_year"] == 366

    def test_monthly_summary_structure(self, sample_inks):
        """Test monthly summary has all expected fields."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["get_current_assignments_summary"]()

        assert len(result["monthly_summary"]) == 12
        jan = result["monthly_summary"][0]
        assert "month" in jan
        assert "month_name" in jan
        assert "days_in_month" in jan
        assert "assigned_days" in jan
        assert "api_assignments" in jan
        assert "session_assignments" in jan
        assert "unassigned_days" in jan


# =============================================================================
# Tests for find_available_inks_for_theme()
# =============================================================================

class TestFindAvailableInksForTheme:
    """Tests for find_available_inks_for_theme tool function."""

    def test_all_inks_unassigned(self, sample_inks):
        """Test with all inks unassigned."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["find_available_inks_for_theme"]()

        assert result["success"] is True
        assert result["matches_returned"] == 5
        for ink in result["available_inks"]:
            assert ink["status"] == "unassigned"

    def test_exclude_session_assigned(self, sample_inks):
        """Test excluding session-assigned inks."""
        tools, _, _, _ = setup_tools(
            inks=sample_inks,
            session={"2026-01-01": 0}
        )
        result = tools["find_available_inks_for_theme"](include_session_assigned=False)

        assert result["matches_returned"] == 4  # Ink 0 excluded
        indices = [ink["index"] for ink in result["available_inks"]]
        assert 0 not in indices

    def test_include_session_assigned_default(self, sample_inks):
        """Test that session-assigned inks are included by default."""
        tools, _, _, _ = setup_tools(
            inks=sample_inks,
            session={"2026-01-01": 0}
        )
        result = tools["find_available_inks_for_theme"]()

        # Ink 0 should be included with status "session_assigned"
        ink_0 = next((i for i in result["available_inks"] if i["index"] == 0), None)
        assert ink_0 is not None
        assert ink_0["status"] == "session_assigned"
        assert ink_0["current_date"] == "2026-01-01"

    def test_api_assigned_never_returned(self, sample_inks):
        """Test that API-assigned inks are never returned."""
        tools, _, _, _ = setup_tools(
            inks=sample_inks,
            api={"2026-01-15": 1}
        )
        result = tools["find_available_inks_for_theme"]()

        indices = [ink["index"] for ink in result["available_inks"]]
        assert 1 not in indices

    def test_query_filter(self, sample_inks):
        """Test filtering by query."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["find_available_inks_for_theme"](query="blue")

        assert result["success"] is True
        # Should find Blue Velvet and Kon-peki (both have "blue" in tags)
        assert result["matches_returned"] >= 1

    def test_color_filter(self, sample_inks):
        """Test filtering by color."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["find_available_inks_for_theme"](color="red")

        assert result["success"] is True
        # Should find Apache Sunset and Oxblood
        assert result["matches_returned"] == 2

    def test_brand_filter(self, sample_inks):
        """Test filtering by brand."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["find_available_inks_for_theme"](brand="Diamine")

        assert result["success"] is True
        assert result["matches_returned"] == 2

    def test_limit_parameter(self, sample_inks):
        """Test limit parameter."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["find_available_inks_for_theme"](limit=2)

        assert result["matches_returned"] == 2

    def test_collection_summary_counts(self, sample_inks):
        """Test collection summary counts."""
        tools, _, _, _ = setup_tools(
            inks=sample_inks,
            session={"2026-01-01": 0},
            api={"2026-01-15": 1}
        )
        result = tools["find_available_inks_for_theme"]()

        summary = result["collection_summary"]
        assert summary["total_inks"] == 5
        assert summary["unassigned"] == 3
        assert summary["session_assigned"] == 1
        assert summary["api_assigned_immovable"] == 1


# =============================================================================
# Tests for set_month_theme()
# =============================================================================

class TestSetMonthTheme:
    """Tests for set_month_theme tool function."""

    def test_invalid_month(self, sample_inks):
        """Test with invalid month."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["set_month_theme"](month=0, theme="Test")

        assert result["success"] is False
        assert "Invalid month" in result["message"]

    def test_empty_theme_name(self, sample_inks):
        """Test with empty theme name."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["set_month_theme"](month=1, theme="")

        assert result["success"] is False
        assert "cannot be empty" in result["message"]

    def test_successful_theme_set(self, sample_inks):
        """Test successful theme setting."""
        tools, _, _, themes_reactive = setup_tools(inks=sample_inks)
        result = tools["set_month_theme"](
            month=1,
            theme="Winter Blues",
            description="Cool tones for cold days"
        )

        assert result["success"] is True
        assert result["theme"] == "Winter Blues"
        assert result["description"] == "Cool tones for cold days"
        # Verify reactive state
        themes = themes_reactive.get()
        assert "2026-01" in themes
        assert themes["2026-01"]["theme"] == "Winter Blues"

    def test_overwrite_existing_theme(self, sample_inks):
        """Test overwriting existing theme."""
        tools, _, _, themes_reactive = setup_tools(
            inks=sample_inks,
            themes={"2026-01": {"theme": "Old Theme", "description": "Old desc"}}
        )
        result = tools["set_month_theme"](
            month=1,
            theme="New Theme",
            description="New desc"
        )

        assert result["success"] is True
        themes = themes_reactive.get()
        assert themes["2026-01"]["theme"] == "New Theme"

    def test_whitespace_trimming(self, sample_inks):
        """Test that whitespace is trimmed."""
        tools, _, _, themes_reactive = setup_tools(inks=sample_inks)
        result = tools["set_month_theme"](
            month=1,
            theme="  Winter Blues  ",
            description="  Cool tones  "
        )

        assert result["theme"] == "Winter Blues"
        assert result["description"] == "Cool tones"


# =============================================================================
# Tests for get_month_theme()
# =============================================================================

class TestGetMonthTheme:
    """Tests for get_month_theme tool function."""

    def test_invalid_month(self, sample_inks):
        """Test with invalid month."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["get_month_theme"](month=13)

        assert result["success"] is False
        assert "Invalid month" in result["message"]

    def test_no_theme_set(self, sample_inks):
        """Test getting theme when none is set."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["get_month_theme"](month=1)

        assert result["success"] is True
        assert result["theme"] is None
        assert "No theme set" in result["message"]

    def test_theme_exists(self, sample_inks):
        """Test getting existing theme."""
        tools, _, _, _ = setup_tools(
            inks=sample_inks,
            themes={"2026-01": {"theme": "Winter Blues", "description": "Cool tones"}}
        )
        result = tools["get_month_theme"](month=1)

        assert result["success"] is True
        assert result["theme"] == "Winter Blues"
        assert result["description"] == "Cool tones"
        assert result["source"] == "session"

    def test_return_structure(self, sample_inks):
        """Test return structure has all expected fields."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["get_month_theme"](month=1)

        assert "month" in result
        assert "month_name" in result
        assert "year" in result
        assert "theme" in result
        assert "description" in result


# =============================================================================
# Tests for clear_month_theme()
# =============================================================================

class TestClearMonthTheme:
    """Tests for clear_month_theme tool function."""

    def test_invalid_month(self, sample_inks):
        """Test with invalid month."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["clear_month_theme"](month=0)

        assert result["success"] is False
        assert "Invalid month" in result["message"]

    def test_nonexistent_theme(self, sample_inks):
        """Test clearing theme that doesn't exist."""
        tools, _, _, _ = setup_tools(inks=sample_inks)
        result = tools["clear_month_theme"](month=1)

        assert result["success"] is True
        assert "No theme was set" in result["message"]

    def test_clear_existing_theme(self, sample_inks):
        """Test clearing existing theme."""
        tools, _, _, themes_reactive = setup_tools(
            inks=sample_inks,
            themes={"2026-01": {"theme": "Winter", "description": ""}}
        )
        result = tools["clear_month_theme"](month=1)

        assert result["success"] is True
        assert "Cleared theme" in result["message"]
        assert "2026-01" not in themes_reactive.get()

    def test_reactive_state_update(self, sample_inks):
        """Test that reactive state is properly updated."""
        tools, _, _, themes_reactive = setup_tools(
            inks=sample_inks,
            themes={
                "2026-01": {"theme": "Winter", "description": ""},
                "2026-02": {"theme": "Valentine", "description": ""}
            }
        )
        tools["clear_month_theme"](month=1)

        themes = themes_reactive.get()
        assert "2026-01" not in themes
        assert "2026-02" in themes  # Other theme preserved


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
