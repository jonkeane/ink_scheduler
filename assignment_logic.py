"""
Core ink assignment logic - pure functions for easy testing
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import numpy as np
import json


def parse_swatch_date_from_comment(comment: str, year: int) -> Optional[str]:
    """
    Parse the comment field to extract a swatch date assignment.

    Looks for JSON like:
    {"swatch2026": {"theme": "All samples", "theme_description": "...", "date": "2026-01-01"}}

    Args:
        comment: The comment text from the ink
        year: The year to look for (e.g., 2026 looks for "swatch2026")

    Returns:
        Date string in YYYY-MM-DD format if found, None otherwise
    """
    if not comment:
        return None

    try:
        # Try to parse as JSON
        data = json.loads(comment)
        swatch_key = f"swatch{year}"

        if swatch_key in data:
            swatch_data = data[swatch_key]

            # Handle both old format (direct string) and new format (object with date field)
            if isinstance(swatch_data, str):
                # Old format: {"swatch2026": "2026-01-01"}
                date_str = swatch_data
            elif isinstance(swatch_data, dict) and "date" in swatch_data:
                # New format: {"swatch2026": {"date": "2026-01-01", ...}}
                date_str = swatch_data["date"]
            else:
                return None

            # Validate it's a valid date string for the correct year
            date = datetime.strptime(date_str, "%Y-%m-%d")
            if date.year == year:
                return date_str
    except (json.JSONDecodeError, ValueError, TypeError, KeyError):
        # Not valid JSON or not a valid date
        pass

    return None


def parse_theme_from_comment(comment: str, year: int) -> Optional[Dict[str, str]]:
    """
    Parse the comment field to extract theme information.

    Looks for JSON like:
    {"swatch2026": {"theme": "All samples", "theme_description": "...", "date": "2026-01-01"}}

    Args:
        comment: The comment text from the ink
        year: The year to look for (e.g., 2026 looks for "swatch2026")

    Returns:
        Dictionary with 'theme' and 'theme_description' if found, None otherwise
    """
    if not comment:
        return None

    try:
        data = json.loads(comment)
        swatch_key = f"swatch{year}"

        if swatch_key in data and isinstance(data[swatch_key], dict):
            swatch_data = data[swatch_key]
            theme = swatch_data.get("theme")
            theme_description = swatch_data.get("theme_description")

            if theme or theme_description:
                return {
                    "theme": theme or "",
                    "theme_description": theme_description or ""
                }
    except (json.JSONDecodeError, ValueError, TypeError, KeyError):
        pass

    return None


def create_yearly_assignments_with_inks(inks: List[Dict], year: int, seed: int = None) -> Dict[str, int]:
    """
    Assign each ink to a unique day of the year, respecting explicit date assignments in comments.

    Inks with explicit swatch dates in their comments (e.g., {"swatch2026": "2026-01-01"})
    will be assigned to those specific dates. Remaining inks are randomly assigned to
    remaining days.

    Args:
        inks: List of ink dictionaries with 'comment' field
        year: The year to create assignments for
        seed: Optional random seed for reproducible assignments

    Returns:
        Dictionary mapping date strings (YYYY-MM-DD) to ink indices (0-based)
    """
    if not inks:
        return {}

    # Set seed for reproducibility if provided
    if seed is not None:
        np.random.seed(seed)

    # Get all days in the year
    start_date = datetime(year, 1, 1)
    end_date = datetime(year, 12, 31)
    num_days = (end_date - start_date).days + 1

    assignments = {}
    assigned_inks = set()
    assigned_dates = set()

    # First pass: handle explicit date assignments from comments
    for ink_idx, ink in enumerate(inks):
        comment = ink.get("comment", "")
        explicit_date = parse_swatch_date_from_comment(comment, year)
        if explicit_date:
            # Only assign if date isn't already taken
            if explicit_date not in assigned_dates:
                assignments[explicit_date] = ink_idx
                assigned_inks.add(ink_idx)
                assigned_dates.add(explicit_date)

    # Second pass: randomly assign remaining inks to remaining dates
    unassigned_inks = [i for i in range(len(inks)) if i not in assigned_inks]
    np.random.shuffle(unassigned_inks)

    # Get all dates that aren't yet assigned
    all_dates = []
    for day_offset in range(num_days):
        date = start_date + timedelta(days=day_offset)
        date_str = date.strftime("%Y-%m-%d")
        if date_str not in assigned_dates:
            all_dates.append(date_str)

    # Assign remaining inks to remaining dates
    for ink_idx, date_str in zip(unassigned_inks, all_dates):
        assignments[date_str] = ink_idx

    return assignments


def create_yearly_assignments(num_inks: int, year: int, seed: int = None) -> Dict[str, int]:
    """
    Assign each ink to a unique day of the year (legacy version without comment parsing).

    Args:
        num_inks: Total number of inks in collection
        year: The year to create assignments for
        seed: Optional random seed for reproducible assignments

    Returns:
        Dictionary mapping date strings (YYYY-MM-DD) to ink indices (0-based)
    """
    if num_inks == 0:
        return {}

    # Set seed for reproducibility if provided
    if seed is not None:
        np.random.seed(seed)

    # Get all days in the year
    start_date = datetime(year, 1, 1)
    end_date = datetime(year, 12, 31)
    num_days = (end_date - start_date).days + 1

    # Shuffle ink indices
    ink_ids = list(range(num_inks))
    np.random.shuffle(ink_ids)

    # Assign one unique ink per day
    assignments = {}
    for day_offset in range(min(num_days, num_inks)):
        date = start_date + timedelta(days=day_offset)
        date_str = date.strftime("%Y-%m-%d")
        assignments[date_str] = ink_ids[day_offset]

    return assignments


def get_month_summary(assignments: Dict[str, int], year: int, month: int) -> List[int]:
    """
    Get all ink indices assigned to a specific month.

    Args:
        assignments: Dictionary mapping date strings to ink indices
        year: Year to filter by
        month: Month to filter by (1-12)

    Returns:
        List of ink indices assigned to days in that month
    """
    month_inks = []
    for date_str, ink_idx in assignments.items():
        date = datetime.strptime(date_str, "%Y-%m-%d")
        if date.year == year and date.month == month:
            month_inks.append(ink_idx)

    return month_inks


def validate_assignments_unique(assignments: Dict[str, int]) -> bool:
    """
    Validate that no ink appears twice in the assignments.

    Args:
        assignments: Dictionary mapping date strings to ink indices

    Returns:
        True if all inks are unique, False otherwise
    """
    ink_indices = list(assignments.values())
    return len(ink_indices) == len(set(ink_indices))
