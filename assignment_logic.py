"""
Core ink assignment logic - pure functions for easy testing
"""
from datetime import datetime
from typing import List, Dict, Optional
import json
import random


def normalize_apostrophes(text: str) -> str:
    """
    Normalize various Unicode punctuation to standard ASCII equivalents.

    LLMs often return "smart" punctuation instead of ASCII characters:
    - Curly apostrophes (' ') instead of straight (')
    - En/em dashes (– —) instead of hyphens (-)
    - Smart quotes (" ") instead of straight (")
    - Non-breaking spaces instead of regular spaces

    This causes ink names like "Cat's Eye Nebula" or "Kon-peki" to fail
    matching when the database uses ASCII but the LLM returns Unicode.

    Args:
        text: Input string that may contain various Unicode punctuation

    Returns:
        String with Unicode punctuation normalized to ASCII equivalents
    """
    # Apostrophe-like characters -> ASCII apostrophe
    apostrophe_chars = [
        '\u2019',  # ' RIGHT SINGLE QUOTATION MARK (most common from LLMs)
        '\u2018',  # ' LEFT SINGLE QUOTATION MARK
        '\u02BC',  # ʼ MODIFIER LETTER APOSTROPHE
        '\u02BB',  # ʻ MODIFIER LETTER TURNED COMMA
        '\u2032',  # ′ PRIME
        '\u0060',  # ` GRAVE ACCENT
        '\u00B4',  # ´ ACUTE ACCENT
    ]
    for char in apostrophe_chars:
        text = text.replace(char, "'")

    # Dash-like characters -> ASCII hyphen-minus
    dash_chars = [
        '\u2013',  # – EN DASH
        '\u2014',  # — EM DASH
        '\u2212',  # − MINUS SIGN
        '\u2010',  # ‐ HYPHEN
        '\u2011',  # ‑ NON-BREAKING HYPHEN
        '\u2012',  # ‒ FIGURE DASH
        '\u2015',  # ― HORIZONTAL BAR
    ]
    for char in dash_chars:
        text = text.replace(char, "-")

    # Double quote characters -> ASCII double quote
    double_quote_chars = [
        '\u201C',  # " LEFT DOUBLE QUOTATION MARK
        '\u201D',  # " RIGHT DOUBLE QUOTATION MARK
        '\u201E',  # „ DOUBLE LOW-9 QUOTATION MARK
        '\u201F',  # ‟ DOUBLE HIGH-REVERSED-9 QUOTATION MARK
    ]
    for char in double_quote_chars:
        text = text.replace(char, '"')

    # Space-like characters -> ASCII space
    space_chars = [
        '\u00A0',  # NO-BREAK SPACE
        '\u2002',  # EN SPACE
        '\u2003',  # EM SPACE
        '\u2009',  # THIN SPACE
        '\u200A',  # HAIR SPACE
    ]
    for char in space_chars:
        text = text.replace(char, ' ')

    return text


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
        "macro_cluster_id": ink.get("macro_cluster_id", ""),
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


def get_ink_identifier(ink: Dict) -> Optional[str]:
    """
    Get the best stable identifier for an ink, with type prefix.

    Prefers macro_cluster_id (prefixed "macro:"), falls back to ink id (prefixed "id:").
    The prefix ensures no collision between the two namespaces.

    Args:
        ink: Ink dictionary

    Returns:
        Prefixed identifier string (e.g., "macro:12345" or "id:674158"), or None if neither available
    """
    macro_id = ink.get("macro_cluster_id")
    if macro_id:
        return f"macro:{macro_id}"
    ink_id = ink.get("id")
    if ink_id:
        return f"id:{ink_id}"
    return None


def parse_ink_identifier(identifier: str) -> tuple[str, str]:
    """
    Parse a prefixed ink identifier into (type, value).

    Args:
        identifier: Prefixed identifier like "macro:12345" or "id:674158"

    Returns:
        (type, value) tuple, e.g., ("macro", "12345") or ("id", "674158")
        Returns ("", "") for empty or invalid identifiers
    """
    if not identifier or ":" not in identifier:
        return ("", "")
    prefix, value = identifier.split(":", 1)
    return (prefix, value)


def build_macro_cluster_lookup(inks: List[Dict]) -> Dict[str, Dict]:
    """
    Build a lookup dictionary from macro_cluster_id to ink dictionary.

    For inks with the same macro_cluster_id (e.g., bottle and sample of same ink),
    this returns the first one found. Use find_ink_by_macro_cluster_id() if you
    need the index as well.

    Args:
        inks: List of ink dictionaries

    Returns:
        Dictionary mapping macro_cluster_id to ink dict
    """
    lookup = {}
    for ink in inks:
        macro_id = ink.get("macro_cluster_id")
        if macro_id and macro_id not in lookup:
            lookup[macro_id] = ink
    return lookup


def find_ink_by_identifier(identifier: str, inks: List[Dict]) -> Optional[tuple]:
    """
    Find an ink by its prefixed identifier.

    Args:
        identifier: Prefixed identifier like "macro:12345" or "id:674158"
        inks: List of ink dictionaries

    Returns:
        (index, ink) tuple if found, None otherwise
    """
    if not identifier:
        return None

    id_type, value = parse_ink_identifier(identifier)

    if id_type == "macro":
        for idx, ink in enumerate(inks):
            if ink.get("macro_cluster_id") == value:
                return (idx, ink)
    elif id_type == "id":
        for idx, ink in enumerate(inks):
            if ink.get("id") == value:
                return (idx, ink)

    return None


# Alias for backwards compatibility
find_ink_by_macro_cluster_id = find_ink_by_identifier


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


def create_explicit_assignments_only(inks: List[Dict], year: int) -> Dict[str, str]:
    """
    Create assignments only for inks with explicit date assignments in private_comment.

    Args:
        inks: List of ink dictionaries with 'private_comment' field
        year: The year to create assignments for

    Returns:
        Dictionary mapping date strings (YYYY-MM-DD) to macro_cluster_id
    """
    if not inks:
        return {}

    assignments = {}
    assigned_dates = set()

    # Check private_comment for assignments (this is where all assignments go)
    for ink in inks:
        private_comment = ink.get("private_comment", "")
        explicit_date = parse_swatch_date_from_comment(private_comment, year)
        ink_identifier = get_ink_identifier(ink)
        if explicit_date and ink_identifier:
            if explicit_date not in assigned_dates:
                assignments[explicit_date] = ink_identifier
                assigned_dates.add(explicit_date)

    return assignments


def get_month_summary(assignments: Dict[str, str], year: int, month: int) -> List[str]:
    """
    Get all macro_cluster_ids assigned to a specific month.

    Args:
        assignments: Dictionary mapping date strings to macro_cluster_ids
        year: Year to filter by
        month: Month to filter by (1-12)

    Returns:
        List of macro_cluster_ids assigned to days in that month
    """
    month_inks = []
    for date_str, macro_cluster_id in assignments.items():
        date = datetime.strptime(date_str, "%Y-%m-%d")
        if date.year == year and date.month == month:
            month_inks.append(macro_cluster_id)

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
    (shortest name containing the query). Normalizes apostrophes to handle
    LLM-generated "smart quotes" vs ASCII apostrophes in database.

    Args:
        ink_name: Name to search for (can be partial)
        inks: List of ink dictionaries

    Returns:
        (index, ink) tuple if found, None otherwise
    """
    # Normalize apostrophes in search query (LLMs often use curly quotes)
    ink_name_lower = normalize_apostrophes(ink_name).lower()

    # First try exact match
    for idx, ink in enumerate(inks):
        brand = normalize_apostrophes(ink.get("brand_name", "")).lower()
        name = normalize_apostrophes(ink.get("name", "")).lower()
        full_name = f"{brand} {name}"

        if ink_name_lower == full_name or ink_name_lower == name:
            return (idx, ink)

    # Then try substring match
    candidates = []
    for idx, ink in enumerate(inks):
        brand = normalize_apostrophes(ink.get("brand_name", "")).lower()
        name = normalize_apostrophes(ink.get("name", "")).lower()
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


def assignable_inks(inks: List[Dict]) -> List[Dict]:
    """
    Return only inks eligible for new assignments (i.e. not archived).

    Archived inks remain in the dataset so previously-set swatches still
    appear on the calendar, but they must not be offered up for picking,
    random selection, or assignment-style search. This helper is the
    single source of truth for that "eligible for assignment" view.

    Args:
        inks: Full list of ink dictionaries

    Returns:
        New list containing only non-archived inks, preserving order
        and dict identity.
    """
    return [ink for ink in inks if not ink.get("archived", False)]


def search_inks(inks: List[Dict], year: int,
                query: Optional[str] = None,
                color: Optional[str] = None,
                brand: Optional[str] = None,
                include_archived: bool = False) -> List[Dict]:
    """
    Search inks by name, color tag, or brand.

    By default archived inks are excluded because this function feeds
    assignment-style flows (picker, chat tools). Pass include_archived=True
    for display-style search across the full collection.

    Args:
        inks: List of ink dictionaries
        year: Year (for checking assignment status)
        query: Optional text to search in ink names
        color: Optional color tag to filter by
        brand: Optional brand name to filter by
        include_archived: Include archived inks in results (default False)

    Returns:
        List of matching ink info dictionaries
    """
    matches = []

    for idx, ink in enumerate(inks):
        if not include_archived and ink.get("archived", False):
            continue

        # Apply filters (normalize apostrophes for LLM compatibility)
        if query:
            full_name = normalize_apostrophes(f"{ink.get('brand_name', '')} {ink.get('name', '')}").lower()
            if normalize_apostrophes(query).lower() not in full_name:
                continue

        if color:
            color_tags = [tag.lower() for tag in ink.get("cluster_tags", [])]
            if color.lower() not in color_tags:
                continue

        if brand:
            ink_brand = normalize_apostrophes(ink.get("brand_name", "")).lower()
            if normalize_apostrophes(brand).lower() not in ink_brand:
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
    session: Dict[str, str],
    api: Dict[str, str],
    from_date: Optional[str],
    to_date: Optional[str],
    macro_cluster_id: Optional[str] = None,
    inks: Optional[List[Dict]] = None
) -> tuple:
    """
    Unified function for all session assignment mutations.

    This is a pure function - it returns a new session dict rather than
    mutating state directly. Callers are responsible for updating reactive state.

    Operations:
    - assign: from_date=None, to_date=set -> assigns ink to date (macro_cluster_id required)
    - unassign: from_date=set, to_date=None -> removes assignment (macro_cluster_id derived from session)
    - move: both set -> moves assignment from one date to another (macro_cluster_id derived from session)

    Args:
        session: Current session assignments {date_str: macro_cluster_id}
        api: API assignments {date_str: macro_cluster_id} (read-only, for protection checks)
        from_date: Source date (None for new assignment)
        to_date: Target date (None for removal)
        macro_cluster_id: Macro cluster ID of ink to assign. Required for assign, optional for unassign/move
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

    # For unassign/move operations, derive macro_cluster_id from session if not provided
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

        # Derive or validate macro_cluster_id
        session_macro_id = session[from_date]
        if macro_cluster_id is None:
            macro_cluster_id = session_macro_id
        elif macro_cluster_id != session_macro_id:
            return session, MoveResult(
                False,
                f"Macro cluster ID mismatch: expected {session_macro_id}, got {macro_cluster_id}",
                from_date=from_date
            )

    # For assign operations, macro_cluster_id is required
    if from_date is None and macro_cluster_id is None:
        return session, MoveResult(False, "macro_cluster_id is required for assign operations")

    # Get ink info now that we have macro_cluster_id resolved
    ink_info = {}
    if inks and macro_cluster_id:
        result = find_ink_by_macro_cluster_id(macro_cluster_id, inks)
        if result:
            idx, ink = result
            ink_info = {
                "macro_cluster_id": macro_cluster_id,
                "ink_idx": idx,
                "ink_brand": ink.get("brand_name", "Unknown"),
                "ink_name": ink.get("name", "Unknown")
            }
        else:
            ink_info = {"macro_cluster_id": macro_cluster_id}

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
        # Refuse to assign archived inks to a new date. They remain in the
        # dataset for display, but new assignments must come from the
        # active/non-archived pool.
        if inks:
            lookup = find_ink_by_macro_cluster_id(macro_cluster_id, inks)
            if lookup and lookup[1].get("archived", False):
                return session, MoveResult(
                    False,
                    f"Cannot assign archived ink to {to_date}.",
                    archived=True, to_date=to_date, **ink_info
                )

        # Check if to_date is API-protected
        if to_date in api:
            return session, MoveResult(
                False,
                f"Date {to_date} has a protected API assignment and cannot be modified.",
                protected=True, to_date=to_date, **ink_info
            )

        # Check if ink is already assigned somewhere
        if macro_cluster_id in merged.values():
            # Find where it's assigned
            assigned_date = next((d for d, mid in merged.items() if mid == macro_cluster_id), None)
            return session, MoveResult(
                False,
                f"Ink is already assigned to {assigned_date}",
                already_assigned=True, assigned_date=assigned_date, **ink_info
            )

        # Check if to_date already has a session assignment (will be overwritten)
        displaced_macro_id = session.get(to_date)

        # Perform assign
        new_session = session.copy()
        new_session[to_date] = macro_cluster_id

        result_data = {"operation": "assign", "to_date": to_date, **ink_info}
        if displaced_macro_id is not None:
            result_data["displaced_macro_cluster_id"] = displaced_macro_id

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
    displaced_macro_id = session.get(to_date)

    # Perform move (atomic: delete from source, add to target)
    new_session = session.copy()
    del new_session[from_date]
    new_session[to_date] = macro_cluster_id

    result_data = {"operation": "move", "from_date": from_date, "to_date": to_date, **ink_info}
    if displaced_macro_id is not None:
        result_data["displaced_macro_cluster_id"] = displaced_macro_id

    return new_session, MoveResult(
        True,
        f"Moved ink from {from_date} to {to_date}",
        **result_data
    )


def swap_ink_assignments(
    session: Dict[str, str],
    api: Dict[str, str],
    date1: str,
    date2: str,
    inks: Optional[List[Dict]] = None
) -> tuple:
    """
    Swap ink assignments between two dates.

    This handles the case where you drag an ink onto another assigned date,
    and both inks should swap positions.

    Args:
        session: Current session assignments {date_str: macro_cluster_id}
        api: API assignments {date_str: macro_cluster_id} (read-only, for protection checks)
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

    # Get macro_cluster_ids from merged assignments
    merged = {**session, **api}
    macro_id1 = merged.get(date1)
    macro_id2 = merged.get(date2)

    if macro_id1 is None:
        return session, MoveResult(False, f"No assignment found for {date1}")
    if macro_id2 is None:
        return session, MoveResult(False, f"No assignment found for {date2}")

    # Get ink info for both
    ink_info = {"macro_cluster_id1": macro_id1, "macro_cluster_id2": macro_id2}
    if inks:
        result1 = find_ink_by_macro_cluster_id(macro_id1, inks)
        if result1:
            idx1, ink1 = result1
            ink_info["ink1_idx"] = idx1
            ink_info["ink1_brand"] = ink1.get("brand_name", "Unknown")
            ink_info["ink1_name"] = ink1.get("name", "Unknown")
        result2 = find_ink_by_macro_cluster_id(macro_id2, inks)
        if result2:
            idx2, ink2 = result2
            ink_info["ink2_idx"] = idx2
            ink_info["ink2_brand"] = ink2.get("brand_name", "Unknown")
            ink_info["ink2_name"] = ink2.get("name", "Unknown")

    # Perform swap
    new_session = session.copy()
    new_session[date1] = macro_id2
    new_session[date2] = macro_id1

    return new_session, MoveResult(
        True,
        f"Swapped inks between {date1} and {date2}",
        operation="swap", date1=date1, date2=date2, **ink_info
    )


def shuffle_month_assignments(
    session: Dict[str, str],
    api: Dict[str, str],
    year: int,
    month: int,
    inks: Optional[List[Dict]] = None,
    rng: Optional[random.Random] = None,
) -> tuple:
    """
    Randomly shuffle ink assignments among session-assigned dates within a month.

    API-protected dates are left untouched. Only session assignments for dates
    in the given month are reshuffled.

    This is a pure function - it returns a new session dict rather than
    mutating state directly.

    Args:
        session: Current session assignments {date_str: macro_cluster_id}
        api: API assignments {date_str: macro_cluster_id} (read-only, never modified)
        year: Year of the target month
        month: Month to shuffle (1-12)
        inks: Optional ink list for including ink info in result
        rng: Optional random.Random instance for deterministic shuffling

    Returns:
        (new_session, MoveResult) tuple
    """
    if not 1 <= month <= 12:
        return session, MoveResult(False, f"Invalid month: {month}. Must be 1-12.")

    if rng is None:
        rng = random.Random()

    # Collect session-assigned dates within this month (excluding API-protected)
    month_dates = []
    for date_str in session:
        if date_str in api:
            continue
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue
        if dt.year == year and dt.month == month:
            month_dates.append(date_str)

    if len(month_dates) < 2:
        return session, MoveResult(
            False,
            f"Need at least 2 session assignments in {year}-{month:02d} to shuffle, found {len(month_dates)}.",
        )

    # Extract the macro_cluster_ids and shuffle them
    macro_ids = [session[d] for d in month_dates]
    rng.shuffle(macro_ids)

    # Build new session with shuffled assignments
    new_session = session.copy()
    for date_str, macro_id in zip(month_dates, macro_ids):
        new_session[date_str] = macro_id

    # Build result info
    result_data: Dict = {"operation": "shuffle", "year": year, "month": month}
    result_data["dates_shuffled"] = sorted(month_dates)
    result_data["count"] = len(month_dates)

    if inks:
        shuffled_details = []
        for date_str in sorted(month_dates):
            macro_id = new_session[date_str]
            info = {"date": date_str, "macro_cluster_id": macro_id}
            result = find_ink_by_macro_cluster_id(macro_id, inks)
            if result:
                idx, ink = result
                info["ink_idx"] = idx
                info["ink_brand"] = ink.get("brand_name", "Unknown")
                info["ink_name"] = ink.get("name", "Unknown")
            shuffled_details.append(info)
        result_data["shuffled_assignments"] = shuffled_details

    return new_session, MoveResult(
        True,
        f"Shuffled {len(month_dates)} ink assignments in {year}-{month:02d}",
        **result_data,
    )

