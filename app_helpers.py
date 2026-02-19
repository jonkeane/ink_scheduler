"""
Pure helper functions extracted from app.py for testability.

These functions contain business logic that can be tested without
the Shiny reactive framework.
"""
from calendar import monthrange
from datetime import datetime
from typing import NamedTuple, Optional

from assignment_logic import create_explicit_assignments_only, parse_theme_from_comment


# =============================================================================
# Date and Button ID Utilities
# =============================================================================

def get_month_dates(year: int, month: int) -> list[str]:
    """
    Get all date strings for a month.

    Args:
        year: Year (e.g., 2026)
        month: Month number (1-12)

    Returns:
        List of date strings in YYYY-MM-DD format
    """
    num_days = monthrange(year, month)[1]
    return [f"{year}-{month:02d}-{day:02d}" for day in range(1, num_days + 1)]


def make_button_id(prefix: str, date_str: str) -> str:
    """
    Generate a button ID from a prefix and date string.

    Replaces dashes with underscores for valid Shiny input IDs.

    Args:
        prefix: Button type prefix (e.g., "remove", "save", "assign")
        date_str: Date in YYYY-MM-DD format

    Returns:
        Button ID string (e.g., "remove_2026_01_15")
    """
    return f"{prefix}_{date_str.replace('-', '_')}"


def detect_new_click(current_clicks: int, prev_clicks: int) -> bool:
    """
    Detect if a button was clicked by comparing click counts.

    Args:
        current_clicks: Current click count from input
        prev_clicks: Previously recorded click count

    Returns:
        True if button was clicked (current > prev)
    """
    return current_clicks > prev_clicks


# =============================================================================
# Cell Data Preparation (for calendar/list views)
# =============================================================================

class CellData(NamedTuple):
    """Data for rendering a calendar or list cell."""
    date_str: str
    day: int
    has_ink: bool
    ink_idx: Optional[int]
    ink_name: str
    ink_brand: str
    ink_color: str
    can_edit: bool  # Session assignment, not API protected
    is_api: bool    # From API (protected)


def prepare_cell_data(
    date_str: str,
    day: int,
    inks: list[dict],
    daily_assignments: dict,
    session_assignments: dict,
    api_assignments: dict
) -> CellData:
    """
    Prepare data for rendering a single calendar/list cell.

    Args:
        date_str: Date in YYYY-MM-DD format
        day: Day number (1-31)
        inks: List of ink dictionaries
        daily_assignments: Merged assignments {date_str: ink_idx}
        session_assignments: Session-only assignments
        api_assignments: API-only assignments (protected)

    Returns:
        CellData with all info needed to render the cell
    """
    ink_idx = daily_assignments.get(date_str)
    has_ink = ink_idx is not None and ink_idx < len(inks)

    if has_ink:
        ink = inks[ink_idx]
        return CellData(
            date_str=date_str,
            day=day,
            has_ink=True,
            ink_idx=ink_idx,
            ink_name=ink.get("name", "Unknown"),
            ink_brand=ink.get("brand_name", ""),
            ink_color=ink.get("color", "#cccccc"),
            can_edit=date_str in session_assignments and date_str not in api_assignments,
            is_api=date_str in api_assignments
        )
    else:
        return CellData(
            date_str=date_str,
            day=day,
            has_ink=False,
            ink_idx=None,
            ink_name="",
            ink_brand="",
            ink_color="",
            can_edit=False,
            is_api=False
        )


def prepare_month_cells(
    year: int,
    month: int,
    inks: list[dict],
    daily_assignments: dict,
    session_assignments: dict,
    api_assignments: dict
) -> list[CellData]:
    """
    Prepare data for all cells in a month.

    Args:
        year: Year
        month: Month (1-12)
        inks: List of ink dictionaries
        daily_assignments: Merged assignments
        session_assignments: Session assignments
        api_assignments: API assignments

    Returns:
        List of CellData for each day of the month
    """
    dates = get_month_dates(year, month)
    return [
        prepare_cell_data(
            date_str, day + 1, inks,
            daily_assignments, session_assignments, api_assignments
        )
        for day, date_str in enumerate(dates)
    ]


# =============================================================================
# Chat System Prompt
# =============================================================================

def get_chat_system_prompt(num_inks: int, year: int) -> str:
    """
    Get the system prompt for the LLM chat assistant.

    Args:
        num_inks: Number of inks in the collection
        year: Year being organized

    Returns:
        System prompt string
    """
    return f"""You are an expert fountain pen ink curator helping organize a collection of {num_inks} inks for the year {year}.

When analyzing an ink collection, consider:
- Color families and harmonies
- Ink brands, lines of inks
- Seasonal appropriateness (e.g., warm colors in fall, pastels in spring, holidays)
- Ink properties (shimmer, sheen, special effects)
- User preferences and stated requirements
- Variety and balance across the year

You have access to tools that let you browse, search, assign, and remove ink assignments.
You can also set themes for months using set_month_theme() - always set a theme after filling a month with inks!

HOLISTIC THEME PLANNING (CRITICAL):
Before proposing any theme, you MUST evaluate whether it can fill the entire month:
1. First, search for inks that would match the theme using search_inks() or find_available_inks_for_theme()
2. Count how many matching inks are available vs. how many days need filling
3. A month typically has 28-31 days. A theme with only 4-5 matching inks is NOT viable on its own.

If a theme cannot fill the month:
- DO NOT propose it as a standalone theme
- Instead, propose a COMBINED theme (e.g., "Blues & Teals" or "Shimmer & Sheen Inks" or "Winter Cool Tones")
- Or broaden the criteria (e.g., instead of "Navy Blue" suggest "Blue Family")
- Or suggest two complementary themes that together fill the month (e.g., "Week 1-2: Warm Reds, Week 3-4: Deep Burgundies")
- You also cannot repeat an ink throughout the year. In fact, the tool calls are set up to make that impossible. If you don't have enough inks for a month, you will need to try harder.

NEVER leave a month partially filled. Every day should have an ink assigned. If the user requests a narrow theme that can't fill the month, explain the coverage gap and propose alternatives that achieve full coverage.

TWO-TIER STATE MANAGEMENT:
- API Assignments: Loaded from the user's saved data. These are PROTECTED and cannot be modified.
- Session Assignments: Your experimental assignments. These can be freely modified but are not auto-saved.

PROTECTION RULES:
- Dates with API assignments are protected - you cannot assign or unassign them
- Session assignments can be freely added or removed
- The user must explicitly save the session to persist your changes

PROACTIVE GAP FILLING:
When you move or reassign inks from one month to another, this often creates gaps (empty slots) in the source month. Be proactive about filling these:
1. After moving inks out of a month, check if it now has unassigned days using get_month_assignments()
2. If there are gaps, use find_available_inks_for_theme() to find inks that could fill them
3. This tool returns both unassigned inks AND session-assigned inks that could be reshuffled
4. Suggest backfilling with inks that match the month's existing theme, or propose adjusting the theme
5. Don't wait for the user to notice empty slots - anticipate and offer to fill them
6. It may take a few rounds of shuffling to optimize the schedule, and that's fine
7. Consider whether moving a session-assigned ink from another month would create a better overall arrangement

Help the user organize their inks by suggesting themes, using tools to make assignments, and being flexible based on feedback."""


# =============================================================================
# Session Format Helpers
# =============================================================================

def parse_session_data(loaded_data: dict) -> tuple[dict, dict]:
    """
    Parse session data, supporting both old and new formats.

    Old format: flat dict {"2026-01-01": 0, ...}
    New format: {"assignments": {...}, "themes": {...}}

    Args:
        loaded_data: Loaded JSON data from session file

    Returns:
        (assignments_dict, themes_dict) tuple
    """
    if "assignments" in loaded_data:
        # New format
        return (
            loaded_data.get("assignments", {}),
            loaded_data.get("themes", {})
        )
    else:
        # Old format - flat dict of assignments
        return loaded_data, {}


# =============================================================================
# Theme Extraction Helpers
# =============================================================================

class ThemeInfo(NamedTuple):
    """Theme information with source tracking."""
    theme: str
    description: str
    source: str  # "session" | "api" | "none"


def get_month_theme(
    year: int,
    month: int,
    session_themes: dict,
    inks: list[dict],
    daily_assignments: dict
) -> ThemeInfo:
    """
    Extract theme for a month with fallback waterfall.

    Priority:
    1. Session themes (editable, takes precedence)
    2. API ink comment on first day of month
    3. No theme available

    Args:
        year: Year (e.g., 2026)
        month: Month number (1-12)
        session_themes: Dict of {month_key: {theme, description}}
        inks: List of ink dictionaries
        daily_assignments: Dict of {date_str: ink_idx}

    Returns:
        ThemeInfo with theme, description, and source
    """
    month_key = f"{year}-{month:02d}"

    # Check session themes first
    if month_key in session_themes:
        theme_data = session_themes[month_key]
        theme_name = theme_data.get("theme", "")
        theme_desc = theme_data.get("description", "")
        if theme_name:
            return ThemeInfo(theme_name, theme_desc, "session")

    # Fall back to API ink comments
    if not inks:
        return ThemeInfo("", "", "none")

    first_day_str = f"{year}-{month:02d}-01"
    first_day_ink_idx = daily_assignments.get(first_day_str)

    if first_day_ink_idx is None or first_day_ink_idx >= len(inks):
        return ThemeInfo("", "", "none")

    first_day_ink = inks[first_day_ink_idx]
    private_comment = first_day_ink.get("private_comment", "")
    theme_info = parse_theme_from_comment(private_comment, year)

    if not theme_info:
        return ThemeInfo("", "", "none")

    return ThemeInfo(
        theme_info["theme"],
        theme_info["theme_description"],
        "api"
    )


# =============================================================================
# Save Operation Helpers
# =============================================================================

class SaveData(NamedTuple):
    """Data prepared for saving an assignment to API."""
    date: str
    theme: str
    theme_description: str
    month_key: str


def prepare_save_data(date_str: str, year: int, themes: dict) -> SaveData:
    """
    Prepare save data by extracting theme for the assignment's month.

    Args:
        date_str: Date in YYYY-MM-DD format
        year: Year (for validation)
        themes: Session themes dict {month_key: {theme, description}}

    Returns:
        SaveData with date, theme, description, and month_key
    """
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    month_key = f"{year}-{date_obj.month:02d}"
    theme_data = themes.get(month_key, {})

    return SaveData(
        date=date_str,
        theme=theme_data.get("theme", ""),
        theme_description=theme_data.get("description", ""),
        month_key=month_key
    )


class PostSaveUpdates(NamedTuple):
    """Updates to apply after successful API save."""
    updated_inks: list[dict]
    new_api_assignments: dict
    new_session_assignments: dict


def prepare_post_save_updates(
    inks: list[dict],
    ink_idx: int,
    updated_comment: str,
    date_str: str,
    year: int,
    current_session: dict
) -> PostSaveUpdates:
    """
    Prepare state updates after successful API save.

    After saving to API:
    1. Update ink's private_comment in local list
    2. Re-parse API assignments from updated inks
    3. Remove date from session (now in API)

    Args:
        inks: Current ink list
        ink_idx: Index of saved ink
        updated_comment: New comment from API
        date_str: Date that was saved
        year: Year for assignment parsing
        current_session: Current session assignments

    Returns:
        PostSaveUpdates with all coordinated changes
    """
    # 1. Update local ink data (create new list to avoid mutation)
    updated_inks = [ink.copy() for ink in inks]
    updated_inks[ink_idx]["private_comment"] = updated_comment

    # 2. Re-parse API assignments
    new_api_assignments = create_explicit_assignments_only(updated_inks, year)

    # 3. Remove from session (now in API)
    new_session = current_session.copy()
    if date_str in new_session:
        del new_session[date_str]

    return PostSaveUpdates(
        updated_inks=updated_inks,
        new_api_assignments=new_api_assignments,
        new_session_assignments=new_session
    )
