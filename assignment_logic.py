"""
Core ink assignment logic - pure functions for easy testing
"""
from datetime import datetime
from typing import List, Dict, Optional
import json


def extract_ink_info(ink: dict, idx: int) -> dict:
    """
    Extract standardized ink information from an ink dictionary.

    This is the single source of truth for what ink fields are exposed
    to the LLM tools. Add new fields here to make them available everywhere.

    Args:
        ink: Raw ink dictionary from the API
        idx: Index of the ink in the collection

    Returns:
        Dictionary with standardized ink information
    """
    return {
        "index": idx,
        "brand": ink.get("brand_name", "Unknown"),
        "name": ink.get("name", "Unknown"),
        "ink_cluster_tags": ink.get("cluster_tags", []),
        "color": ink.get("color", ""),
        "line_name": ink.get("line_name", ""),
        "kind": ink.get("kind", ""),
        "used": ink.get("used", False),
        "usage_count": ink.get("usage_count", 0),
        "last_used_on": ink.get("last_used_on", ""),
        "comment": ink.get("comment", ""),
    }


def parse_comment_json(comment: Optional[str]) -> Dict:
    """
    Parse a comment field as JSON, returning empty dict if invalid.

    Args:
        comment: The comment string (may be None or invalid JSON)

    Returns:
        Parsed dictionary, or empty dict if parsing fails
    """
    if not comment:
        return {}
    try:
        return json.loads(comment)
    except (json.JSONDecodeError, TypeError):
        return {}


def get_swatch_data(comment: Optional[str], year: int) -> Optional[Dict]:
    """
    Get the swatch data for a given year from a comment.

    Args:
        comment: The comment text (JSON string)
        year: The year to look for (e.g., 2026 looks for "swatch2026")

    Returns:
        The swatch data dict if found, None otherwise
    """
    data = parse_comment_json(comment)
    swatch_key = f"swatch{year}"
    swatch_data = data.get(swatch_key)
    if isinstance(swatch_data, dict):
        return swatch_data
    return None


def parse_swatch_date_from_comment(comment: str, year: int) -> Optional[str]:
    """
    Parse the comment field to extract a swatch date assignment.

    Args:
        comment: The comment text from the ink
        year: The year to look for (e.g., 2026 looks for "swatch2026")

    Returns:
        Date string in YYYY-MM-DD format if found, None otherwise
    """
    swatch_data = get_swatch_data(comment, year)
    if not swatch_data or "date" not in swatch_data:
        return None

    date_str = swatch_data["date"]
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
        if date.year == year:
            return date_str
    except ValueError:
        pass
    return None


def parse_theme_from_comment(comment: str, year: int) -> Optional[Dict[str, str]]:
    """
    Parse the comment field to extract theme information.

    Args:
        comment: The comment text from the ink
        year: The year to look for (e.g., 2026 looks for "swatch2026")

    Returns:
        Dictionary with 'theme' and 'theme_description' if found, None otherwise
    """
    swatch_data = get_swatch_data(comment, year)
    if not swatch_data:
        return None

    theme = swatch_data.get("theme")
    theme_description = swatch_data.get("theme_description")

    if theme or theme_description:
        return {
            "theme": theme or "",
            "theme_description": theme_description or ""
        }
    return None


def check_overwrite_conflict(ink: Dict, year: int) -> Optional[Dict]:
    """
    Check if saving would overwrite existing swatch data for this year.

    Args:
        ink: Ink dictionary with 'private_comment' field
        year: Year to check (e.g., 2026)

    Returns:
        None if no conflict (safe to save), or dict with conflict details:
        {
            "existing_date": str,
            "existing_theme": str or None,
            "existing_theme_description": str or None
        }
    """
    existing_swatch = get_swatch_data(ink.get("private_comment"), year)
    if not existing_swatch:
        return None

    existing_date = existing_swatch.get("date")
    if not existing_date:
        return None

    return {
        "existing_date": existing_date,
        "existing_theme": existing_swatch.get("theme"),
        "existing_theme_description": existing_swatch.get("theme_description")
    }


def build_swatch_comment_json(
    existing_comment: Optional[str],
    year: int,
    date: str,
    theme: Optional[str] = None,
    theme_description: Optional[str] = None
) -> str:
    """
    Build updated private_comment JSON, preserving existing data.

    Merges new swatch data for the specified year with any existing
    private_comment data (other years, other fields).

    Args:
        existing_comment: Current private_comment value (may be None or invalid JSON)
        year: Year for the swatch key (e.g., 2026 -> "swatch2026")
        date: Date string in YYYY-MM-DD format
        theme: Optional theme name
        theme_description: Optional theme description

    Returns:
        JSON string with merged data
    """
    # Parse existing comment, defaulting to empty dict
    data = parse_comment_json(existing_comment)

    # Build new swatch data
    swatch_key = f"swatch{year}"
    swatch_data = {"date": date}

    # Only include theme fields if they have values
    if theme:
        swatch_data["theme"] = theme
    if theme_description:
        swatch_data["theme_description"] = theme_description

    # Update the swatch data for this year
    data[swatch_key] = swatch_data

    return json.dumps(data)


def remove_swatch_from_comment(existing_comment: Optional[str], year: int) -> str:
    """
    Remove swatch data for a specific year from private_comment JSON.

    Preserves all other data in the comment (other years, other fields).

    Args:
        existing_comment: Current private_comment value (may be None or invalid JSON)
        year: Year to remove (e.g., 2026 -> removes "swatch2026")

    Returns:
        JSON string with swatch data removed, or empty object "{}" if nothing remains
    """
    # Parse existing comment, defaulting to empty dict
    data = parse_comment_json(existing_comment)

    # Remove the swatch key for this year
    swatch_key = f"swatch{year}"
    if swatch_key in data:
        del data[swatch_key]

    # Return updated JSON (could be empty object if that was the only data)
    return json.dumps(data) if data else "{}"


def create_explicit_assignments_only(inks: List[Dict], year: int) -> Dict[str, int]:
    """
    Create assignments only for inks with explicit date assignments in private_comment.

    Args:
        inks: List of ink dictionaries with 'private_comment' field
        year: The year to create assignments for

    Returns:
        Dictionary mapping date strings (YYYY-MM-DD) to ink indices (0-based)
    """
    if not inks:
        return {}

    assignments = {}
    assigned_dates = set()

    # Check private_comment for assignments (this is where all assignments go)
    for ink_idx, ink in enumerate(inks):
        private_comment = ink.get("private_comment", "")
        explicit_date = parse_swatch_date_from_comment(private_comment, year)
        if explicit_date:
            if explicit_date not in assigned_dates:
                assignments[explicit_date] = ink_idx
                assigned_dates.add(explicit_date)

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


def has_assignment(ink: Dict, year: int) -> bool:
    """
    Check if an ink has an assignment for the given year.

    Args:
        ink: Ink dictionary with 'private_comment' field
        year: Year to check

    Returns:
        True if ink has a date assignment for this year
    """
    swatch_data = get_swatch_data(ink.get("private_comment"), year)
    return swatch_data is not None and "date" in swatch_data


def find_ink_by_name(ink_name: str, inks: List[Dict]) -> Optional[tuple]:
    """
    Find an ink by name using case-insensitive substring matching.

    Tries exact match first, then substring match. Returns best match
    (shortest name containing the query).

    Args:
        ink_name: Name to search for (can be partial)
        inks: List of ink dictionaries

    Returns:
        (index, ink) tuple if found, None otherwise
    """
    ink_name_lower = ink_name.lower()

    # First try exact match
    for idx, ink in enumerate(inks):
        brand = ink.get("brand_name", "").lower()
        name = ink.get("name", "").lower()
        full_name = f"{brand} {name}"

        if ink_name_lower == full_name or ink_name_lower == name:
            return (idx, ink)

    # Then try substring match
    candidates = []
    for idx, ink in enumerate(inks):
        brand = ink.get("brand_name", "").lower()
        name = ink.get("name", "").lower()
        full_name = f"{brand} {name}"

        if ink_name_lower in full_name or ink_name_lower in name:
            candidates.append((idx, ink))

    if len(candidates) == 1:
        return candidates[0]
    elif len(candidates) > 1:
        # Return best match (shortest name that contains the query)
        candidates.sort(key=lambda x: len(x[1].get("name", "")))
        return candidates[0]

    return None


def search_inks(inks: List[Dict], year: int,
                query: Optional[str] = None,
                color: Optional[str] = None,
                brand: Optional[str] = None) -> List[Dict]:
    """
    Search inks by name, color tag, or brand.

    Args:
        inks: List of ink dictionaries
        year: Year (for checking assignment status)
        query: Optional text to search in ink names
        color: Optional color tag to filter by
        brand: Optional brand name to filter by

    Returns:
        List of matching ink info dictionaries
    """
    matches = []

    for idx, ink in enumerate(inks):
        # Apply filters
        if query:
            full_name = f"{ink.get('brand_name', '')} {ink.get('name', '')}".lower()
            if query.lower() not in full_name:
                continue

        if color:
            color_tags = [tag.lower() for tag in ink.get("cluster_tags", [])]
            if color.lower() not in color_tags:
                continue

        if brand:
            if brand.lower() not in ink.get("brand_name", "").lower():
                continue

        ink_info = extract_ink_info(ink, idx)
        ink_info["already_assigned"] = has_assignment(ink, year)
        matches.append(ink_info)

    return matches


# =============================================================================
# Unified session assignment mutation
# =============================================================================

class MoveResult:
    """Result of a move_ink_assignment operation."""
    def __init__(self, success: bool, message: str, **kwargs):
        self.success = success
        self.message = message
        self.data = kwargs

    def to_dict(self) -> Dict:
        return {"success": self.success, "message": self.message, **self.data}


def move_ink_assignment(
    session: Dict[str, int],
    api: Dict[str, int],
    from_date: Optional[str],
    to_date: Optional[str],
    ink_idx: Optional[int] = None,
    inks: Optional[List[Dict]] = None
) -> tuple:
    """
    Unified function for all session assignment mutations.

    This is a pure function - it returns a new session dict rather than
    mutating state directly. Callers are responsible for updating reactive state.

    Operations:
    - assign: from_date=None, to_date=set -> assigns ink to date (ink_idx required)
    - unassign: from_date=set, to_date=None -> removes assignment (ink_idx derived from session)
    - move: both set -> moves assignment from one date to another (ink_idx derived from session)

    Args:
        session: Current session assignments {date_str: ink_idx}
        api: API assignments {date_str: ink_idx} (read-only, for protection checks)
        from_date: Source date (None for new assignment)
        to_date: Target date (None for removal)
        ink_idx: Index of ink to assign. Required for assign, optional for unassign/move
                 (will be derived from session[from_date] if not provided)
        inks: Optional ink list for including ink info in result

    Returns:
        (new_session, MoveResult) tuple
        - new_session: Updated session dict (or original if failed)
        - MoveResult: Result object with success, message, and metadata
    """
    # Validate: must have at least one of from_date or to_date
    if from_date is None and to_date is None:
        return session, MoveResult(False, "Must specify from_date or to_date")

    # Validate date formats
    for date_str, label in [(from_date, "from_date"), (to_date, "to_date")]:
        if date_str is not None:
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                return session, MoveResult(False, f"Invalid {label} format: {date_str}. Use YYYY-MM-DD.")

    # For unassign/move operations, derive ink_idx from session if not provided
    if from_date is not None:
        # Check if from_date is API-protected (applies to both unassign and move)
        if from_date in api:
            return session, MoveResult(
                False,
                f"Date {from_date} has a protected API assignment and cannot be modified.",
                protected=True, from_date=from_date
            )

        # Check if from_date has a session assignment
        if from_date not in session:
            return session, MoveResult(
                False,
                f"No session assignment found for {from_date}",
                from_date=from_date
            )

        # Derive or validate ink_idx
        session_ink_idx = session[from_date]
        if ink_idx is None:
            ink_idx = session_ink_idx
        elif ink_idx != session_ink_idx:
            return session, MoveResult(
                False,
                f"Ink index mismatch: expected {session_ink_idx}, got {ink_idx}",
                from_date=from_date
            )

    # For assign operations, ink_idx is required
    if from_date is None and ink_idx is None:
        return session, MoveResult(False, "ink_idx is required for assign operations")

    # Get ink info now that we have ink_idx resolved
    ink_info = {}
    if inks and ink_idx is not None and 0 <= ink_idx < len(inks):
        ink = inks[ink_idx]
        ink_info = {
            "ink_idx": ink_idx,
            "ink_brand": ink.get("brand_name", "Unknown"),
            "ink_name": ink.get("name", "Unknown")
        }

    # Merge for checking what's currently assigned
    merged = {**session, **api}

    # === UNASSIGN (from_date set, to_date None) ===
    if to_date is None:

        # Perform unassign
        new_session = session.copy()
        del new_session[from_date]
        return new_session, MoveResult(
            True,
            f"Removed assignment from {from_date}",
            operation="unassign", from_date=from_date, **ink_info
        )

    # === ASSIGN (from_date None, to_date set) ===
    if from_date is None:
        # Check if to_date is API-protected
        if to_date in api:
            return session, MoveResult(
                False,
                f"Date {to_date} has a protected API assignment and cannot be modified.",
                protected=True, to_date=to_date, **ink_info
            )

        # Check if ink is already assigned somewhere
        if ink_idx in merged.values():
            # Find where it's assigned
            assigned_date = next((d for d, idx in merged.items() if idx == ink_idx), None)
            return session, MoveResult(
                False,
                f"Ink is already assigned to {assigned_date}",
                already_assigned=True, assigned_date=assigned_date, **ink_info
            )

        # Check if to_date already has a session assignment (will be overwritten)
        displaced_ink_idx = session.get(to_date)

        # Perform assign
        new_session = session.copy()
        new_session[to_date] = ink_idx

        result_data = {"operation": "assign", "to_date": to_date, **ink_info}
        if displaced_ink_idx is not None:
            result_data["displaced_ink_idx"] = displaced_ink_idx

        return new_session, MoveResult(
            True,
            f"Assigned ink to {to_date}",
            **result_data
        )

    # === MOVE (both from_date and to_date set) ===
    # from_date validation already done above

    # Check if to_date is API-protected
    if to_date in api:
        return session, MoveResult(
            False,
            f"Date {to_date} has a protected API assignment and cannot be used as destination.",
            protected=True, to_date=to_date, **ink_info
        )

    # Check if to_date already has a session assignment (will be displaced)
    displaced_ink_idx = session.get(to_date)

    # Perform move (atomic: delete from source, add to target)
    new_session = session.copy()
    del new_session[from_date]
    new_session[to_date] = ink_idx

    result_data = {"operation": "move", "from_date": from_date, "to_date": to_date, **ink_info}
    if displaced_ink_idx is not None:
        result_data["displaced_ink_idx"] = displaced_ink_idx

    return new_session, MoveResult(
        True,
        f"Moved ink from {from_date} to {to_date}",
        **result_data
    )


def swap_ink_assignments(
    session: Dict[str, int],
    api: Dict[str, int],
    date1: str,
    date2: str,
    inks: Optional[List[Dict]] = None
) -> tuple:
    """
    Swap ink assignments between two dates.

    This handles the case where you drag an ink onto another assigned date,
    and both inks should swap positions.

    Args:
        session: Current session assignments {date_str: ink_idx}
        api: API assignments {date_str: ink_idx} (read-only, for protection checks)
        date1: First date (source of drag)
        date2: Second date (drop target)
        inks: Optional ink list for including ink info in result

    Returns:
        (new_session, MoveResult) tuple
    """
    # Validate date formats
    for date_str, label in [(date1, "date1"), (date2, "date2")]:
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return session, MoveResult(False, f"Invalid {label} format: {date_str}. Use YYYY-MM-DD.")

    # Check if either date is API-protected
    if date1 in api:
        return session, MoveResult(
            False,
            f"Date {date1} has a protected API assignment and cannot be modified.",
            protected=True, date=date1
        )
    if date2 in api:
        return session, MoveResult(
            False,
            f"Date {date2} has a protected API assignment and cannot be modified.",
            protected=True, date=date2
        )

    # Get ink indices from session
    merged = {**session, **api}
    ink_idx1 = merged.get(date1)
    ink_idx2 = merged.get(date2)

    if ink_idx1 is None:
        return session, MoveResult(False, f"No assignment found for {date1}")
    if ink_idx2 is None:
        return session, MoveResult(False, f"No assignment found for {date2}")

    # Get ink info for both
    ink_info = {}
    if inks:
        if 0 <= ink_idx1 < len(inks):
            ink1 = inks[ink_idx1]
            ink_info["ink1_idx"] = ink_idx1
            ink_info["ink1_brand"] = ink1.get("brand_name", "Unknown")
            ink_info["ink1_name"] = ink1.get("name", "Unknown")
        if 0 <= ink_idx2 < len(inks):
            ink2 = inks[ink_idx2]
            ink_info["ink2_idx"] = ink_idx2
            ink_info["ink2_brand"] = ink2.get("brand_name", "Unknown")
            ink_info["ink2_name"] = ink2.get("name", "Unknown")

    # Perform swap
    new_session = session.copy()
    new_session[date1] = ink_idx2
    new_session[date2] = ink_idx1

    return new_session, MoveResult(
        True,
        f"Swapped inks between {date1} and {date2}",
        operation="swap", date1=date1, date2=date2, **ink_info
    )


