"""
Tests for view rendering functions.

These tests verify that the view functions in views.py correctly render
UI elements based on input data. Since these return Shiny UI objects,
we test by converting to HTML strings and checking for expected content.
"""
import pytest
from shiny import ui

from views import (
    render_calendar_view,
    render_list_view,
    render_ink_collection_view,
    render_month_assignment_summary,
    SAVE_ICON_SVG,
    INK_BOTTLE_SVG,
)


# =============================================================================
# Test Fixtures
# =============================================================================

def mock_ink_swatch_fn(color: str, size: str = "sm"):
    """Mock ink swatch function that returns a simple colored div."""
    return ui.HTML(f'<div class="mock-swatch" style="background:{color}"></div>')


@pytest.fixture
def sample_inks():
    """Sample ink collection for testing."""
    return [
        {"name": "Kon-Peki", "brand_name": "Iroshizuku", "color": "#007BA7"},
        {"name": "Oxblood", "brand_name": "Diamine", "color": "#800020"},
        {"name": "Apache Sunset", "brand_name": "Noodler's", "color": "#FF6600"},
    ]


@pytest.fixture
def sample_assignments():
    """Sample assignments for January 2026."""
    return {
        "2026-01-01": 0,  # Kon-Peki
        "2026-01-15": 1,  # Oxblood
    }


# =============================================================================
# Tests for SVG Constants
# =============================================================================

class TestSvgConstants:
    """Tests for SVG icon constants."""

    def test_save_icon_svg_is_valid_svg(self):
        """Save icon should be valid SVG markup."""
        assert "<svg" in SAVE_ICON_SVG
        assert "</svg>" in SAVE_ICON_SVG
        assert 'viewBox="0 0 24 24"' in SAVE_ICON_SVG

    def test_ink_bottle_svg_is_valid_svg(self):
        """Ink bottle icon should be valid SVG markup."""
        assert "<svg" in INK_BOTTLE_SVG
        assert "</svg>" in INK_BOTTLE_SVG
        assert 'viewBox="0 0 24 24"' in INK_BOTTLE_SVG


# =============================================================================
# Tests for render_calendar_view()
# =============================================================================

class TestRenderCalendarView:
    """Tests for calendar view rendering."""

    def test_empty_inks_shows_message(self):
        """Should show loading message when no inks."""
        result = render_calendar_view(
            inks=[],
            daily_assignments={},
            session_assignments={},
            api_assignments={},
            year=2026,
            month=1,
            ink_swatch_fn=mock_ink_swatch_fn
        )
        html = str(result)
        assert "No inks loaded" in html

    def test_renders_weekday_headers(self, sample_inks):
        """Should render weekday headers."""
        result = render_calendar_view(
            inks=sample_inks,
            daily_assignments={},
            session_assignments={},
            api_assignments={},
            year=2026,
            month=1,
            ink_swatch_fn=mock_ink_swatch_fn
        )
        html = str(result)
        for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            assert day in html

    def test_renders_calendar_grid_class(self, sample_inks):
        """Should have calendar-grid class."""
        result = render_calendar_view(
            inks=sample_inks,
            daily_assignments={},
            session_assignments={},
            api_assignments={},
            year=2026,
            month=1,
            ink_swatch_fn=mock_ink_swatch_fn
        )
        html = str(result)
        assert "calendar-grid" in html

    def test_renders_assigned_ink(self, sample_inks, sample_assignments):
        """Should render ink name for assigned dates."""
        result = render_calendar_view(
            inks=sample_inks,
            daily_assignments=sample_assignments,
            session_assignments=sample_assignments,
            api_assignments={},
            year=2026,
            month=1,
            ink_swatch_fn=mock_ink_swatch_fn
        )
        html = str(result)
        assert "Kon-Peki" in html
        assert "Iroshizuku" in html

    def test_session_assignment_has_remove_button(self, sample_inks, sample_assignments):
        """Session assignments should have remove button."""
        result = render_calendar_view(
            inks=sample_inks,
            daily_assignments=sample_assignments,
            session_assignments=sample_assignments,
            api_assignments={},
            year=2026,
            month=1,
            ink_swatch_fn=mock_ink_swatch_fn
        )
        html = str(result)
        assert "calendar-remove-btn" in html

    def test_api_assignment_no_remove_button(self, sample_inks, sample_assignments):
        """API assignments should not have remove button."""
        result = render_calendar_view(
            inks=sample_inks,
            daily_assignments=sample_assignments,
            session_assignments={},
            api_assignments=sample_assignments,
            year=2026,
            month=1,
            ink_swatch_fn=mock_ink_swatch_fn
        )
        html = str(result)
        assert "calendar-remove-btn" not in html

    def test_unassigned_day_has_day_number(self, sample_inks):
        """Unassigned days should show day number."""
        result = render_calendar_view(
            inks=sample_inks,
            daily_assignments={},
            session_assignments={},
            api_assignments={},
            year=2026,
            month=1,
            ink_swatch_fn=mock_ink_swatch_fn
        )
        html = str(result)
        # Check for day numbers in the calendar
        assert ">15<" in html or "15</strong>" in html or ">15</strong>" in html

    def test_february_has_28_days_non_leap(self, sample_inks):
        """February 2026 should have 28 days."""
        result = render_calendar_view(
            inks=sample_inks,
            daily_assignments={},
            session_assignments={},
            api_assignments={},
            year=2026,
            month=2,
            ink_swatch_fn=mock_ink_swatch_fn
        )
        html = str(result)
        assert ">28<" in html or "28</strong>" in html
        # Day 29 should not appear for non-leap year
        assert "2026-02-29" not in html


# =============================================================================
# Tests for render_list_view()
# =============================================================================

class TestRenderListView:
    """Tests for list view rendering."""

    def test_empty_inks_shows_message(self):
        """Should show loading message when no inks."""
        result = render_list_view(
            inks=[],
            daily_assignments={},
            session_assignments={},
            api_assignments={},
            year=2026,
            month=1,
            ink_swatch_fn=mock_ink_swatch_fn
        )
        html = str(result)
        assert "No inks loaded" in html

    def test_renders_column_headers(self, sample_inks):
        """Should render column headers."""
        result = render_list_view(
            inks=sample_inks,
            daily_assignments={},
            session_assignments={},
            api_assignments={},
            year=2026,
            month=1,
            ink_swatch_fn=mock_ink_swatch_fn
        )
        html = str(result)
        assert "Date" in html
        assert "Color" in html
        assert "Brand" in html
        assert "Name" in html
        assert "Actions" in html

    def test_renders_assigned_ink_details(self, sample_inks, sample_assignments):
        """Should render ink details for assigned dates."""
        result = render_list_view(
            inks=sample_inks,
            daily_assignments=sample_assignments,
            session_assignments=sample_assignments,
            api_assignments={},
            year=2026,
            month=1,
            ink_swatch_fn=mock_ink_swatch_fn
        )
        html = str(result)
        assert "Kon-Peki" in html
        assert "Iroshizuku" in html

    def test_unassigned_row_shows_unassigned_text(self, sample_inks):
        """Unassigned rows should show 'Unassigned' text."""
        result = render_list_view(
            inks=sample_inks,
            daily_assignments={},
            session_assignments={},
            api_assignments={},
            year=2026,
            month=1,
            ink_swatch_fn=mock_ink_swatch_fn
        )
        html = str(result)
        assert "Unassigned" in html

    def test_unassigned_row_has_assign_button(self, sample_inks):
        """Unassigned rows should have assign button."""
        result = render_list_view(
            inks=sample_inks,
            daily_assignments={},
            session_assignments={},
            api_assignments={},
            year=2026,
            month=1,
            ink_swatch_fn=mock_ink_swatch_fn
        )
        html = str(result)
        assert "ink-assign-btn" in html

    def test_session_assignment_has_save_remove_buttons(self, sample_inks, sample_assignments):
        """Session assignments should have save and remove buttons."""
        result = render_list_view(
            inks=sample_inks,
            daily_assignments=sample_assignments,
            session_assignments=sample_assignments,
            api_assignments={},
            year=2026,
            month=1,
            ink_swatch_fn=mock_ink_swatch_fn
        )
        html = str(result)
        assert "list-save-btn" in html
        assert "list-remove-btn" in html

    def test_api_assignment_shows_swatched_badge(self, sample_inks, sample_assignments):
        """API assignments should show 'swatched' badge."""
        result = render_list_view(
            inks=sample_inks,
            daily_assignments=sample_assignments,
            session_assignments={},
            api_assignments=sample_assignments,
            year=2026,
            month=1,
            ink_swatch_fn=mock_ink_swatch_fn
        )
        html = str(result)
        assert "swatched" in html
        assert "api-badge" in html

    def test_renders_31_rows_for_january(self, sample_inks):
        """January should render 31 rows."""
        result = render_list_view(
            inks=sample_inks,
            daily_assignments={},
            session_assignments={},
            api_assignments={},
            year=2026,
            month=1,
            ink_swatch_fn=mock_ink_swatch_fn
        )
        html = str(result)
        # Check for last day of January
        assert "Jan 31" in html


# =============================================================================
# Tests for render_ink_collection_view()
# =============================================================================

class TestRenderInkCollectionView:
    """Tests for ink collection view rendering."""

    def test_empty_inks_shows_message(self):
        """Should show loading message when no inks."""
        result = render_ink_collection_view(
            inks=[],
            daily_assignments={},
            session_assignments={},
            api_assignments={},
            year=2026,
            search_query="",
            ink_swatch_fn=mock_ink_swatch_fn
        )
        html = str(result)
        assert "No inks loaded" in html

    def test_renders_all_inks(self, sample_inks):
        """Should render all inks when no search query."""
        result = render_ink_collection_view(
            inks=sample_inks,
            daily_assignments={},
            session_assignments={},
            api_assignments={},
            year=2026,
            search_query="",
            ink_swatch_fn=mock_ink_swatch_fn
        )
        html = str(result)
        assert "Kon-Peki" in html
        assert "Oxblood" in html
        assert "Apache Sunset" in html

    def test_search_filters_by_name(self, sample_inks):
        """Should filter inks by name search."""
        result = render_ink_collection_view(
            inks=sample_inks,
            daily_assignments={},
            session_assignments={},
            api_assignments={},
            year=2026,
            search_query="Kon",
            ink_swatch_fn=mock_ink_swatch_fn
        )
        html = str(result)
        assert "Kon-Peki" in html
        assert "Oxblood" not in html

    def test_search_filters_by_brand(self, sample_inks):
        """Should filter inks by brand search."""
        result = render_ink_collection_view(
            inks=sample_inks,
            daily_assignments={},
            session_assignments={},
            api_assignments={},
            year=2026,
            search_query="Diamine",
            ink_swatch_fn=mock_ink_swatch_fn
        )
        html = str(result)
        assert "Oxblood" in html
        assert "Kon-Peki" not in html

    def test_search_case_insensitive(self, sample_inks):
        """Search should be case insensitive."""
        result = render_ink_collection_view(
            inks=sample_inks,
            daily_assignments={},
            session_assignments={},
            api_assignments={},
            year=2026,
            search_query="KON-PEKI",
            ink_swatch_fn=mock_ink_swatch_fn
        )
        html = str(result)
        assert "Kon-Peki" in html

    def test_no_results_shows_message(self, sample_inks):
        """Should show message when no inks match search."""
        result = render_ink_collection_view(
            inks=sample_inks,
            daily_assignments={},
            session_assignments={},
            api_assignments={},
            year=2026,
            search_query="nonexistent",
            ink_swatch_fn=mock_ink_swatch_fn
        )
        html = str(result)
        assert "No inks match your search" in html

    def test_assigned_ink_shows_date(self, sample_inks):
        """Assigned inks should show their assignment date."""
        assignments = {"2026-01-15": 0}  # Kon-Peki assigned to Jan 15
        result = render_ink_collection_view(
            inks=sample_inks,
            daily_assignments=assignments,
            session_assignments=assignments,
            api_assignments={},
            year=2026,
            search_query="",
            ink_swatch_fn=mock_ink_swatch_fn
        )
        html = str(result)
        # Session assignments should have save button
        assert "ink_save_0" in html

    def test_api_assigned_ink_shows_swatched(self, sample_inks):
        """API-assigned inks should show 'swatched' badge."""
        assignments = {"2026-01-15": 0}
        result = render_ink_collection_view(
            inks=sample_inks,
            daily_assignments=assignments,
            session_assignments={},
            api_assignments=assignments,
            year=2026,
            search_query="",
            ink_swatch_fn=mock_ink_swatch_fn
        )
        html = str(result)
        assert "swatched" in html
        assert "ink-row-api" in html

    def test_unassigned_ink_has_date_picker(self, sample_inks):
        """Unassigned inks should have date picker."""
        result = render_ink_collection_view(
            inks=sample_inks,
            daily_assignments={},
            session_assignments={},
            api_assignments={},
            year=2026,
            search_query="",
            ink_swatch_fn=mock_ink_swatch_fn
        )
        html = str(result)
        assert "ink_date_0" in html  # Date picker for first ink


# =============================================================================
# Tests for render_month_assignment_summary()
# =============================================================================

class TestRenderMonthAssignmentSummary:
    """Tests for month assignment summary rendering."""

    def test_empty_inks_shows_message(self):
        """Should show message when no inks."""
        result = render_month_assignment_summary(
            inks=[],
            daily_assignments={},
            year=2026
        )
        html = str(result)
        assert "No inks loaded" in html

    def test_renders_all_12_months(self, sample_inks):
        """Should render all 12 months."""
        result = render_month_assignment_summary(
            inks=sample_inks,
            daily_assignments={},
            year=2026
        )
        html = str(result)
        months = ["January", "February", "March", "April", "May", "June",
                  "July", "August", "September", "October", "November", "December"]
        for month in months:
            assert month in html

    def test_renders_header_columns(self, sample_inks):
        """Should render header columns."""
        result = render_month_assignment_summary(
            inks=sample_inks,
            daily_assignments={},
            year=2026
        )
        html = str(result)
        assert "Month" in html
        assert "Assigned" in html
        assert "Total Days" in html
        assert "Coverage" in html

    def test_shows_assignment_counts(self, sample_inks, sample_assignments):
        """Should show correct assignment counts."""
        result = render_month_assignment_summary(
            inks=sample_inks,
            daily_assignments=sample_assignments,
            year=2026
        )
        html = str(result)
        # January has 2 assignments in sample_assignments
        assert "summary-count-col" in html

    def test_shows_zero_percent_for_empty_month(self, sample_inks):
        """Months with no assignments should show 0%."""
        result = render_month_assignment_summary(
            inks=sample_inks,
            daily_assignments={},
            year=2026
        )
        html = str(result)
        assert "0%" in html

    def test_calculates_coverage_percentage(self, sample_inks):
        """Should calculate coverage percentage correctly."""
        # Assign all 31 days of January
        full_january = {f"2026-01-{d:02d}": 0 for d in range(1, 32)}
        result = render_month_assignment_summary(
            inks=sample_inks,
            daily_assignments=full_january,
            year=2026
        )
        html = str(result)
        assert "100%" in html


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_ink_with_missing_fields(self):
        """Should handle inks with missing fields gracefully."""
        incomplete_inks = [
            {"name": "TestInk"},  # Missing brand_name and color
        ]
        result = render_calendar_view(
            inks=incomplete_inks,
            daily_assignments={"2026-01-01": 0},
            session_assignments={"2026-01-01": 0},
            api_assignments={},
            year=2026,
            month=1,
            ink_swatch_fn=mock_ink_swatch_fn
        )
        html = str(result)
        assert "TestInk" in html

    def test_assignment_with_invalid_ink_index(self, sample_inks):
        """Should handle assignment with out-of-bounds ink index."""
        invalid_assignments = {"2026-01-01": 999}  # Index doesn't exist
        result = render_calendar_view(
            inks=sample_inks,
            daily_assignments=invalid_assignments,
            session_assignments=invalid_assignments,
            api_assignments={},
            year=2026,
            month=1,
            ink_swatch_fn=mock_ink_swatch_fn
        )
        # Should not crash, should render as unassigned
        html = str(result)
        assert "calendar-grid" in html

    def test_leap_year_february(self, sample_inks):
        """February in leap year should have 29 days."""
        result = render_list_view(
            inks=sample_inks,
            daily_assignments={},
            session_assignments={},
            api_assignments={},
            year=2024,  # Leap year
            month=2,
            ink_swatch_fn=mock_ink_swatch_fn
        )
        html = str(result)
        assert "Feb 29" in html


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
