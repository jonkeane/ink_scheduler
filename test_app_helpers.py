"""
Tests for testable helper functions extracted from app.py.

These tests cover pure functions and logic that can be tested
without setting up the full Shiny reactive framework.
"""
import pytest
import json
import tempfile
import os

from app import ink_swatch_svg
from app_helpers import (
    parse_session_data,
    get_month_theme,
    ThemeInfo,
    prepare_save_data,
    SaveData,
    prepare_post_save_updates,
    PostSaveUpdates,
    get_month_dates,
    make_button_id,
    detect_new_click,
    prepare_cell_data,
    prepare_month_cells,
    CellData,
    get_chat_system_prompt,
)


# =============================================================================
# Tests for ink_swatch_svg()
# =============================================================================

class TestInkSwatchSvg:
    """Tests for ink_swatch_svg function."""

    def test_hex_color(self):
        """Test with hex color value."""
        result = ink_swatch_svg("#ff0000", "sm")
        svg_str = str(result)

        assert "<svg" in svg_str
        assert 'fill="#ff0000"' in svg_str

    def test_css_color_name(self):
        """Test with CSS color name."""
        result = ink_swatch_svg("blue", "sm")
        svg_str = str(result)

        assert "<svg" in svg_str
        assert 'fill="blue"' in svg_str

    def test_size_sm_dimensions(self):
        """Test small size has correct dimensions."""
        result = ink_swatch_svg("#000000", "sm")
        svg_str = str(result)

        assert 'width="32"' in svg_str
        assert 'height="24"' in svg_str
        assert 'viewBox="0 0 100 75"' in svg_str

    def test_size_lg_dimensions(self):
        """Test large size has correct dimensions."""
        result = ink_swatch_svg("#000000", "lg")
        svg_str = str(result)

        assert 'width="80"' in svg_str
        assert 'height="50"' in svg_str
        assert 'viewBox="0 0 100 90"' in svg_str

    def test_svg_structure_contains_path(self):
        """Test SVG contains path element with fill."""
        result = ink_swatch_svg("#123456", "sm")
        svg_str = str(result)

        assert "<path" in svg_str
        assert "fill=" in svg_str
        assert "</svg>" in svg_str

    def test_empty_color_string(self):
        """Test with empty color string (should still work)."""
        result = ink_swatch_svg("", "sm")
        svg_str = str(result)

        # Empty color is still valid SVG (browser will use default)
        assert "<svg" in svg_str
        assert 'fill=""' in svg_str


# =============================================================================
# Tests for session format parsing logic
# =============================================================================

class TestSessionFormatParsing:
    """Tests for session load/save format handling.

    The app supports two formats:
    - New format: {"assignments": {...}, "themes": {...}}
    - Old format: flat dict of assignments
    """

    def test_new_format_complete(self):
        """Test parsing new format with both assignments and themes."""
        data = {
            "assignments": {"2026-01-01": 0, "2026-01-15": 1},
            "themes": {"2026-01": {"theme": "Winter", "description": "Cold"}}
        }
        assignments, themes = parse_session_data(data)

        assert assignments == {"2026-01-01": 0, "2026-01-15": 1}
        assert themes == {"2026-01": {"theme": "Winter", "description": "Cold"}}

    def test_old_format_flat_dict(self):
        """Test parsing old format (flat dict of assignments)."""
        data = {"2026-01-01": 0, "2026-02-14": 4}
        assignments, themes = parse_session_data(data)

        assert assignments == {"2026-01-01": 0, "2026-02-14": 4}
        assert themes == {}

    def test_empty_assignments(self):
        """Test new format with empty assignments."""
        data = {"assignments": {}, "themes": {}}
        assignments, themes = parse_session_data(data)

        assert assignments == {}
        assert themes == {}

    def test_empty_themes(self):
        """Test new format with assignments but no themes."""
        data = {"assignments": {"2026-01-01": 0}, "themes": {}}
        assignments, themes = parse_session_data(data)

        assert assignments == {"2026-01-01": 0}
        assert themes == {}

    def test_missing_themes_key(self):
        """Test new format with missing themes key."""
        data = {"assignments": {"2026-01-01": 0}}
        assignments, themes = parse_session_data(data)

        assert assignments == {"2026-01-01": 0}
        assert themes == {}

    def test_malformed_json_handling(self):
        """Test that malformed JSON raises appropriate error."""
        with pytest.raises(json.JSONDecodeError):
            json.loads("not valid json")

    def test_file_read_write_round_trip(self):
        """Test that session data survives write/read cycle."""
        original_data = {
            "assignments": {"2026-01-01": 0, "2026-02-14": 1},
            "themes": {"2026-01": {"theme": "Test", "description": "Desc"}}
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(original_data, f)
            temp_path = f.name

        try:
            with open(temp_path, 'r') as f:
                loaded_data = json.load(f)

            assignments, themes = parse_session_data(loaded_data)
            assert assignments == original_data["assignments"]
            assert themes == original_data["themes"]
        finally:
            os.unlink(temp_path)

    def test_utf8_encoding(self):
        """Test that UTF-8 characters are handled correctly."""
        data = {
            "assignments": {},
            "themes": {"2026-01": {"theme": "Tëst Thème", "description": "Ünïcödé"}}
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
            temp_path = f.name

        try:
            with open(temp_path, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)

            _, themes = parse_session_data(loaded_data)
            assert themes["2026-01"]["theme"] == "Tëst Thème"
            assert themes["2026-01"]["description"] == "Ünïcödé"
        finally:
            os.unlink(temp_path)


# =============================================================================
# Tests for merged assignments logic
# =============================================================================

class TestMergedAssignmentsLogic:
    """Tests for the assignment merging logic.

    The app merges session and API assignments with API taking precedence.
    """

    def get_merged_assignments(self, session, api):
        """
        Helper that mimics the merge logic from app.py.

        API assignments take precedence over session assignments.
        """
        return {**session, **api}

    def test_session_only(self):
        """Test with only session assignments."""
        session = {"2026-01-01": 0, "2026-01-15": 1}
        api = {}
        merged = self.get_merged_assignments(session, api)

        assert merged == {"2026-01-01": 0, "2026-01-15": 1}

    def test_api_only(self):
        """Test with only API assignments."""
        session = {}
        api = {"2026-01-01": 0, "2026-01-15": 1}
        merged = self.get_merged_assignments(session, api)

        assert merged == {"2026-01-01": 0, "2026-01-15": 1}

    def test_overlapping_keys_api_precedence(self):
        """Test that API takes precedence on overlapping dates."""
        session = {"2026-01-01": 5, "2026-01-15": 6}  # Session values
        api = {"2026-01-01": 0}  # API overrides session for this date
        merged = self.get_merged_assignments(session, api)

        # API value should win for 2026-01-01
        assert merged["2026-01-01"] == 0
        # Session value should remain for 2026-01-15
        assert merged["2026-01-15"] == 6

    def test_both_empty(self):
        """Test with both empty."""
        session = {}
        api = {}
        merged = self.get_merged_assignments(session, api)

        assert merged == {}


# =============================================================================
# Tests for save conflict preparation logic
# =============================================================================

class TestSaveConflictLogic:
    """Tests for save conflict detection logic.

    Tests the pattern used in handle_save_assignment() for
    preparing save data and detecting conflicts.
    """

    def test_no_theme_for_month(self):
        """Test preparing save data when no theme exists."""
        result = prepare_save_data("2026-01-15", 2026, {})

        assert result.date == "2026-01-15"
        assert result.theme == ""
        assert result.theme_description == ""
        assert result.month_key == "2026-01"

    def test_with_theme_for_month(self):
        """Test preparing save data when theme exists."""
        themes = {
            "2026-01": {"theme": "Winter Blues", "description": "Cool tones"}
        }
        result = prepare_save_data("2026-01-15", 2026, themes)

        assert result.date == "2026-01-15"
        assert result.theme == "Winter Blues"
        assert result.theme_description == "Cool tones"

    def test_month_key_generation(self):
        """Test that month key is correctly generated from date."""
        themes = {
            "2026-02": {"theme": "Valentine", "description": ""}
        }
        result = prepare_save_data("2026-02-14", 2026, themes)

        assert result.theme == "Valentine"
        assert result.month_key == "2026-02"

    def test_date_parsing(self):
        """Test various date formats are parsed correctly."""
        themes = {"2026-12": {"theme": "December", "description": ""}}

        result = prepare_save_data("2026-12-25", 2026, themes)
        assert result.date == "2026-12-25"
        assert result.theme == "December"


# =============================================================================
# Tests for get_month_theme()
# =============================================================================

class TestGetMonthTheme:
    """Tests for theme extraction waterfall logic."""

    def test_session_theme_takes_priority(self):
        """Session theme should take precedence over API."""
        session_themes = {
            "2026-01": {"theme": "Session Theme", "description": "From session"}
        }
        # Even with inks that have themes, session should win
        inks = [{"private_comment": '{"swatch2026":{"theme":"API Theme","theme_description":"From API"}}'}]
        daily = {"2026-01-01": 0}

        result = get_month_theme(2026, 1, session_themes, inks, daily)

        assert result.theme == "Session Theme"
        assert result.description == "From session"
        assert result.source == "session"

    def test_api_fallback_when_no_session(self):
        """Falls back to API when no session theme."""
        session_themes = {}
        inks = [{"private_comment": '{"swatch2026":{"theme":"API Theme","theme_description":"From API"}}'}]
        daily = {"2026-01-01": 0}

        result = get_month_theme(2026, 1, session_themes, inks, daily)

        assert result.theme == "API Theme"
        assert result.description == "From API"
        assert result.source == "api"

    def test_no_theme_when_empty(self):
        """Returns 'none' source when no theme available."""
        result = get_month_theme(2026, 1, {}, [], {})

        assert result.theme == ""
        assert result.description == ""
        assert result.source == "none"

    def test_no_theme_when_no_first_day_assignment(self):
        """Returns 'none' when first day has no assignment."""
        session_themes = {}
        inks = [{"private_comment": ""}]
        daily = {"2026-01-15": 0}  # Not the first day

        result = get_month_theme(2026, 1, session_themes, inks, daily)

        assert result.source == "none"

    def test_no_theme_when_ink_has_no_theme_comment(self):
        """Returns 'none' when ink has no theme in comment."""
        session_themes = {}
        inks = [{"private_comment": "Just a plain comment"}]
        daily = {"2026-01-01": 0}

        result = get_month_theme(2026, 1, session_themes, inks, daily)

        assert result.source == "none"

    def test_session_empty_theme_falls_through(self):
        """Session with empty theme name should fall through to API."""
        session_themes = {
            "2026-01": {"theme": "", "description": ""}  # Empty theme
        }
        inks = [{"private_comment": '{"swatch2026":{"theme":"API Theme","theme_description":"Desc"}}'}]
        daily = {"2026-01-01": 0}

        result = get_month_theme(2026, 1, session_themes, inks, daily)

        assert result.theme == "API Theme"
        assert result.source == "api"


# =============================================================================
# Tests for prepare_post_save_updates()
# =============================================================================

class TestPreparePostSaveUpdates:
    """Tests for post-save state coordination."""

    def test_updates_ink_comment(self):
        """Ink comment should be updated in the returned list."""
        inks = [
            {"id": 1, "private_comment": "old comment"},
            {"id": 2, "private_comment": "other ink"}
        ]
        result = prepare_post_save_updates(
            inks, ink_idx=0, updated_comment="new comment",
            date_str="2026-01-01", year=2026, current_session={}
        )

        assert result.updated_inks[0]["private_comment"] == "new comment"
        assert result.updated_inks[1]["private_comment"] == "other ink"

    def test_removes_date_from_session(self):
        """Saved date should be removed from session assignments."""
        inks = [{"id": 1, "private_comment": ""}]
        current_session = {"2026-01-01": 0, "2026-01-15": 1}

        result = prepare_post_save_updates(
            inks, ink_idx=0, updated_comment="new",
            date_str="2026-01-01", year=2026, current_session=current_session
        )

        assert "2026-01-01" not in result.new_session_assignments
        assert "2026-01-15" in result.new_session_assignments

    def test_preserves_other_session_assignments(self):
        """Other session assignments should be preserved."""
        inks = [{"id": 1, "private_comment": ""}]
        current_session = {"2026-01-01": 0, "2026-02-14": 1, "2026-03-01": 2}

        result = prepare_post_save_updates(
            inks, ink_idx=0, updated_comment="new",
            date_str="2026-01-01", year=2026, current_session=current_session
        )

        assert result.new_session_assignments == {"2026-02-14": 1, "2026-03-01": 2}

    def test_does_not_mutate_original_inks(self):
        """Original ink list should not be mutated."""
        inks = [{"id": 1, "private_comment": "original"}]
        original_comment = inks[0]["private_comment"]

        prepare_post_save_updates(
            inks, ink_idx=0, updated_comment="new",
            date_str="2026-01-01", year=2026, current_session={}
        )

        assert inks[0]["private_comment"] == original_comment

    def test_handles_missing_date_in_session(self):
        """Should handle case where date isn't in session."""
        inks = [{"id": 1, "private_comment": ""}]
        current_session = {"2026-02-14": 1}  # Different date

        result = prepare_post_save_updates(
            inks, ink_idx=0, updated_comment="new",
            date_str="2026-01-01", year=2026, current_session=current_session
        )

        # Should not raise, session unchanged
        assert result.new_session_assignments == {"2026-02-14": 1}


# =============================================================================
# Tests for date/button utilities
# =============================================================================

class TestDateUtilities:
    """Tests for date and button ID utilities."""

    def test_get_month_dates_january(self):
        """January should have 31 dates."""
        dates = get_month_dates(2026, 1)
        assert len(dates) == 31
        assert dates[0] == "2026-01-01"
        assert dates[-1] == "2026-01-31"

    def test_get_month_dates_february_non_leap(self):
        """February 2026 (non-leap) should have 28 dates."""
        dates = get_month_dates(2026, 2)
        assert len(dates) == 28
        assert dates[-1] == "2026-02-28"

    def test_get_month_dates_february_leap(self):
        """February 2024 (leap) should have 29 dates."""
        dates = get_month_dates(2024, 2)
        assert len(dates) == 29
        assert dates[-1] == "2024-02-29"

    def test_make_button_id(self):
        """Button ID should replace dashes with underscores."""
        assert make_button_id("remove", "2026-01-15") == "remove_2026_01_15"
        assert make_button_id("save", "2026-12-25") == "save_2026_12_25"
        assert make_button_id("assign", "2026-02-14") == "assign_2026_02_14"

    def test_detect_new_click_true(self):
        """Should detect new click when current > prev."""
        assert detect_new_click(1, 0) is True
        assert detect_new_click(5, 4) is True

    def test_detect_new_click_false(self):
        """Should not detect click when current <= prev."""
        assert detect_new_click(0, 0) is False
        assert detect_new_click(3, 3) is False
        assert detect_new_click(2, 5) is False


# =============================================================================
# Tests for cell data preparation
# =============================================================================

class TestCellDataPreparation:
    """Tests for calendar/list cell data preparation."""

    def test_prepare_cell_data_with_ink(self):
        """Cell with assigned ink should have ink details."""
        inks = [{"name": "Kon-Peki", "brand_name": "Iroshizuku", "color": "#007BA7"}]
        daily = {"2026-01-15": 0}
        session = {"2026-01-15": 0}
        api = {}

        cell = prepare_cell_data("2026-01-15", 15, inks, daily, session, api)

        assert cell.has_ink is True
        assert cell.ink_name == "Kon-Peki"
        assert cell.ink_brand == "Iroshizuku"
        assert cell.ink_color == "#007BA7"
        assert cell.can_edit is True
        assert cell.is_api is False

    def test_prepare_cell_data_api_protected(self):
        """API assignment should be marked as protected."""
        inks = [{"name": "Test", "brand_name": "Brand", "color": "#000"}]
        daily = {"2026-01-15": 0}
        session = {}
        api = {"2026-01-15": 0}

        cell = prepare_cell_data("2026-01-15", 15, inks, daily, session, api)

        assert cell.has_ink is True
        assert cell.can_edit is False
        assert cell.is_api is True

    def test_prepare_cell_data_empty(self):
        """Cell without ink should be empty."""
        cell = prepare_cell_data("2026-01-15", 15, [], {}, {}, {})

        assert cell.has_ink is False
        assert cell.ink_name == ""
        assert cell.can_edit is False

    def test_prepare_month_cells(self):
        """Should prepare cells for entire month."""
        inks = [{"name": "Ink1", "brand_name": "B1", "color": "#111"}]
        daily = {"2026-01-01": 0}
        session = {"2026-01-01": 0}
        api = {}

        cells = prepare_month_cells(2026, 1, inks, daily, session, api)

        assert len(cells) == 31
        assert cells[0].has_ink is True  # Jan 1 has ink
        assert cells[1].has_ink is False  # Jan 2 doesn't


# =============================================================================
# Tests for chat system prompt
# =============================================================================

class TestChatSystemPrompt:
    """Tests for LLM system prompt generation."""

    def test_prompt_contains_ink_count(self):
        """Prompt should include the ink count."""
        prompt = get_chat_system_prompt(150, 2026)
        assert "150 inks" in prompt

    def test_prompt_contains_year(self):
        """Prompt should include the year."""
        prompt = get_chat_system_prompt(100, 2026)
        assert "2026" in prompt

    def test_prompt_contains_key_instructions(self):
        """Prompt should contain key instruction sections."""
        prompt = get_chat_system_prompt(100, 2026)
        assert "HOLISTIC THEME PLANNING" in prompt
        assert "TWO-TIER STATE MANAGEMENT" in prompt
        assert "PROTECTION RULES" in prompt
        assert "PROACTIVE GAP FILLING" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
