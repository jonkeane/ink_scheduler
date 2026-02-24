"""
Tool functions for LLM chat to interact with ink assignments.

These are thin wrappers around assignment_logic.py functions that:
- Bind to reactive state (ink_data, session_assignments, api_assignments)
- Handle reactive updates to session state
- Format responses for the LLM

Session assignments are experimental and not auto-persisted.
API assignments (from ink_cache) are protected and read-only.

Session format:
{
    "assignments": { "2026-02-01": 18, ... },
    "themes": {
        "2026-02": { "theme": "Blues", "description": "Cool winter tones" },
        ...
    }
}
"""
from typing import List, Dict, Optional, Any
import calendar

from assignment_logic import (
    extract_ink_info,
    find_ink_by_name,
    search_inks as search_inks_pure,
    move_ink_assignment,
)


def create_tool_functions(ink_data_reactive, selected_year_reactive,
                          session_assignments_reactive, api_assignments_reactive,
                          session_themes_reactive=None):
    """
    Create tool functions bound to reactive state.

    Args:
        ink_data_reactive: Reactive value containing list of inks
        selected_year_reactive: Reactive value containing selected year
        session_assignments_reactive: Reactive value for session assignments {date: ink_idx}
        api_assignments_reactive: Reactive value for API assignments {date: ink_idx} (read-only)
        session_themes_reactive: Reactive value for session themes {month_key: {theme, description}}

    Returns:
        Tuple of (tool_functions_list, snapshot_updater_function)
        Call the snapshot_updater before each stream_async() call.
    """
    # Snapshot storage for async-safe access
    _snapshot = {
        "inks": [],
        "year": 2026,
        "session": {},
        "api": {},
        "themes": {}
    }

    def update_snapshot():
        """Update snapshot from reactive values. Call before stream_async()."""
        _snapshot["inks"] = ink_data_reactive.get()
        _snapshot["year"] = selected_year_reactive.get()
        _snapshot["session"] = session_assignments_reactive.get().copy()
        _snapshot["api"] = api_assignments_reactive.get().copy()
        if session_themes_reactive is not None:
            _snapshot["themes"] = session_themes_reactive.get().copy()

    def _get_merged_assignments():
        """Get merged view of API + session assignments. API takes precedence."""
        return {**_snapshot["session"], **_snapshot["api"]}

    def list_all_inks() -> Dict[str, Any]:
        """
        List all inks in the collection with their basic information.

        Returns a summary of all available inks including brand, name, color tags,
        and whether they're already assigned for the current year.
        """
        inks = _snapshot["inks"]

        if not inks:
            return {"success": False, "message": "No inks available in collection"}

        merged = _get_merged_assignments()
        assigned_indices = set(merged.values())

        ink_list = []
        for idx, ink in enumerate(inks):
            ink_info = extract_ink_info(ink, idx)
            ink_info["already_assigned"] = idx in assigned_indices
            ink_list.append(ink_info)

        return {"success": True, "total_inks": len(inks), "inks": ink_list}

    def search_inks(query: Optional[str] = None, color: Optional[str] = None,
                    brand: Optional[str] = None) -> Dict[str, Any]:
        """
        Search for inks by name, color tag, or brand.

        Args:
            query: Optional text to search in ink names
            color: Optional color tag to filter by (e.g., "blue", "green")
            brand: Optional brand name to filter by

        Returns matches with their index numbers and current assignment status.
        """
        inks = _snapshot["inks"]
        year = _snapshot["year"]

        if not inks:
            return {"success": False, "message": "No inks available in collection"}

        # Get base matches from pure function
        matches = search_inks_pure(inks, year, query, color, brand)

        # Update assignment status based on merged assignments
        merged = _get_merged_assignments()
        assigned_indices = set(merged.values())

        for match in matches:
            match["already_assigned"] = match["index"] in assigned_indices

        return {"success": True, "matches_found": len(matches), "matches": matches}

    def get_month_assignments(month: int, year: Optional[int] = None) -> Dict[str, Any]:
        """
        Get all ink assignments for a specific month.

        Args:
            month: Month number (1-12)
            year: Year (defaults to currently selected year)

        Returns information about which inks are assigned to which dates in that month.
        """
        if year is None:
            year = _snapshot["year"]

        if not 1 <= month <= 12:
            return {"success": False, "message": f"Invalid month: {month}. Must be 1-12."}

        inks = _snapshot["inks"]
        if not inks:
            return {"success": False, "message": "No inks available in collection"}

        merged = _get_merged_assignments()
        api = _snapshot["api"]
        days_in_month = calendar.monthrange(year, month)[1]

        # Filter to this month
        assignments = []
        for date_str, ink_idx in merged.items():
            if date_str.startswith(f"{year}-{month:02d}-") and ink_idx < len(inks):
                day = int(date_str.split("-")[2])
                ink = inks[ink_idx]
                assignments.append({
                    "date": date_str,
                    "day": day,
                    "ink_index": ink_idx,
                    "brand": ink.get("brand_name", "Unknown"),
                    "name": ink.get("name", "Unknown"),
                    "protected": date_str in api  # From API = protected
                })

        assignments.sort(key=lambda x: x["day"])

        return {
            "success": True,
            "month": month,
            "month_name": calendar.month_name[month],
            "year": year,
            "days_in_month": days_in_month,
            "assigned_days": len(assignments),
            "unassigned_days": days_in_month - len(assignments),
            "assignments": assignments
        }

    def assign_ink_to_date(ink_identifier: str, date_str: str,
                           theme: Optional[str] = None,
                           theme_description: Optional[str] = None) -> Dict[str, Any]:
        """
        Assign a specific ink to a specific date.

        Args:
            ink_identifier: Ink name or brand + name (e.g., "Diamine Blue" or "Blue Velvet")
            date_str: Date in YYYY-MM-DD format
            theme: Optional theme name (ignored in session mode)
            theme_description: Optional description (ignored in session mode)

        Returns success status and details. Will NOT modify dates that already have
        API assignments (protected).
        """
        inks = _snapshot["inks"]

        if not inks:
            return {"success": False, "message": "No inks available in collection"}

        # Find the ink first
        result = find_ink_by_name(ink_identifier, inks)
        if not result:
            return {"success": False, "message": f"Could not find ink matching '{ink_identifier}'."}

        idx, ink = result

        # Use unified move function (assign = move with from_date=None)
        session = _snapshot["session"]
        api = _snapshot["api"]

        new_session, move_result = move_ink_assignment(
            session=session,
            api=api,
            from_date=None,
            to_date=date_str,
            ink_idx=idx,
            inks=inks
        )

        if not move_result.success:
            return move_result.to_dict()

        # Update reactive state and snapshot
        session_assignments_reactive.set(new_session)
        _snapshot["session"] = new_session.copy()

        return {
            "success": True,
            "message": f"Assigned '{ink.get('brand_name')} {ink.get('name')}' to {date_str}",
            "ink_index": idx,
            "date": date_str,
            "note": "This is a session assignment. Use Save Session to persist."
        }

    def bulk_assign_month(ink_identifiers: List[str], month: int, year: Optional[int] = None,
                          theme: Optional[str] = None,
                          theme_description: Optional[str] = None) -> Dict[str, Any]:
        """
        Assign multiple inks to dates across a month.

        Args:
            ink_identifiers: List of ink names to assign
            month: Month number (1-12)
            year: Year (defaults to currently selected year)
            theme: Optional theme name (ignored in session mode)
            theme_description: Optional theme description (ignored in session mode)

        Distributes the inks across available days in the month. Will NOT modify
        dates that have API assignments (protected).
        """
        if year is None:
            year = _snapshot["year"]

        if not 1 <= month <= 12:
            return {"success": False, "message": f"Invalid month: {month}. Must be 1-12."}

        inks = _snapshot["inks"]
        if not inks:
            return {"success": False, "message": "No inks available in collection"}

        days_in_month = calendar.monthrange(year, month)[1]
        merged = _get_merged_assignments()

        # Find available days (not in merged assignments)
        occupied_days = set()
        for date_str in merged.keys():
            if date_str.startswith(f"{year}-{month:02d}-"):
                day = int(date_str.split("-")[2])
                occupied_days.add(day)

        available_days = [d for d in range(1, days_in_month + 1) if d not in occupied_days]

        if len(ink_identifiers) > len(available_days):
            return {
                "success": False,
                "message": f"Not enough days. Need {len(ink_identifiers)}, only {len(available_days)} available.",
                "available_days": len(available_days)
            }

        successful, failed, already_assigned = [], [], []
        session = _snapshot["session"].copy()
        assigned_indices = set(merged.values())

        for i, ink_id in enumerate(ink_identifiers):
            if i >= len(available_days):
                break

            result = find_ink_by_name(ink_id, inks)
            if not result:
                failed.append({"ink_identifier": ink_id, "reason": "Ink not found"})
                continue

            idx, ink = result

            if idx in assigned_indices:
                already_assigned.append({
                    "ink_identifier": ink_id,
                    "ink_index": idx,
                    "brand": ink.get("brand_name"),
                    "name": ink.get("name")
                })
                continue

            day = available_days[i]
            date_str = f"{year}-{month:02d}-{day:02d}"

            session[date_str] = idx
            assigned_indices.add(idx)

            successful.append({
                "ink_index": idx,
                "brand": ink.get("brand_name"),
                "name": ink.get("name"),
                "date": date_str,
                "day": day
            })

        if successful:
            session_assignments_reactive.set(session)
            _snapshot["session"] = session.copy()

        return {
            "success": len(successful) > 0,
            "message": f"Bulk assignment to {calendar.month_name[month]} {year} complete",
            "month": month,
            "month_name": calendar.month_name[month],
            "year": year,
            "successful_assignments": len(successful),
            "failed_assignments": len(failed),
            "already_assigned_inks": len(already_assigned),
            "successful": successful,
            "failed": failed,
            "already_assigned": already_assigned,
            "note": "These are session assignments. Use Save Session to persist."
        }

    def unassign_ink_from_date(date_str: str) -> Dict[str, Any]:
        """
        Remove an ink assignment from a specific date.

        Args:
            date_str: Date in YYYY-MM-DD format to clear

        Will NOT remove API assignments (protected). Only removes session assignments.
        """
        # Use unified move function - it handles all validation and derives ink_idx
        new_session, move_result = move_ink_assignment(
            session=_snapshot["session"],
            api=_snapshot["api"],
            from_date=date_str,
            to_date=None,
            inks=_snapshot["inks"]
        )

        if not move_result.success:
            return move_result.to_dict()

        # Update reactive state and snapshot
        session_assignments_reactive.set(new_session)
        _snapshot["session"] = new_session.copy()

        return {
            "success": True,
            "message": f"Removed session assignment for {date_str}",
            "date": date_str,
            "ink_brand": move_result.data.get("ink_brand"),
            "ink_name": move_result.data.get("ink_name")
        }

    def clear_month_assignments(month: int, year: Optional[int] = None) -> Dict[str, Any]:
        """
        Remove all session ink assignments for a specific month.

        Args:
            month: Month number (1-12)
            year: Year (defaults to currently selected year)

        Will NOT remove API assignments (protected). Only clears session assignments.
        """
        if year is None:
            year = _snapshot["year"]

        if not 1 <= month <= 12:
            return {"success": False, "message": f"Invalid month: {month}. Must be 1-12."}

        inks = _snapshot["inks"]
        session = _snapshot["session"]
        api = _snapshot["api"]

        removed = []
        protected = []
        new_session = session.copy()

        month_prefix = f"{year}-{month:02d}-"

        # Check API assignments for protected count
        for date_str, ink_idx in api.items():
            if date_str.startswith(month_prefix) and ink_idx < len(inks):
                ink = inks[ink_idx]
                protected.append({
                    "date": date_str,
                    "brand": ink.get("brand_name"),
                    "name": ink.get("name"),
                    "reason": "Protected (from API)"
                })

        # Remove session assignments for this month
        for date_str, ink_idx in list(session.items()):
            if date_str.startswith(month_prefix):
                ink = inks[ink_idx] if ink_idx < len(inks) else {}
                removed.append({
                    "date": date_str,
                    "day": int(date_str.split("-")[2]),
                    "brand": ink.get("brand_name"),
                    "name": ink.get("name")
                })
                del new_session[date_str]

        if removed:
            session_assignments_reactive.set(new_session)
            _snapshot["session"] = new_session.copy()

        return {
            "success": len(removed) > 0 or len(protected) == 0,
            "message": f"Cleared session assignments for {calendar.month_name[month]} {year}",
            "month": month,
            "month_name": calendar.month_name[month],
            "year": year,
            "removed_count": len(removed),
            "protected_count": len(protected),
            "removed": removed,
            "protected": protected
        }

    def get_current_assignments_summary(year: Optional[int] = None) -> Dict[str, Any]:
        """
        Get a summary of all assignments for the year.

        Args:
            year: Year (defaults to currently selected year)

        Returns overview of how many inks are assigned per month and overall statistics.
        """
        if year is None:
            year = _snapshot["year"]

        inks = _snapshot["inks"]
        if not inks:
            return {"success": False, "message": "No inks available in collection"}

        merged = _get_merged_assignments()
        api = _snapshot["api"]

        monthly_counts = {month: {"total": 0, "api": 0, "session": 0} for month in range(1, 13)}
        total_assigned = 0

        for date_str, ink_idx in merged.items():
            try:
                parts = date_str.split("-")
                if int(parts[0]) == year:
                    month = int(parts[1])
                    monthly_counts[month]["total"] += 1
                    if date_str in api:
                        monthly_counts[month]["api"] += 1
                    else:
                        monthly_counts[month]["session"] += 1
                    total_assigned += 1
            except (ValueError, IndexError):
                pass

        monthly_summary = []
        for month in range(1, 13):
            days_in_month = calendar.monthrange(year, month)[1]
            counts = monthly_counts[month]
            monthly_summary.append({
                "month": month,
                "month_name": calendar.month_name[month],
                "days_in_month": days_in_month,
                "assigned_days": counts["total"],
                "api_assignments": counts["api"],
                "session_assignments": counts["session"],
                "unassigned_days": days_in_month - counts["total"]
            })

        total_days = sum(calendar.monthrange(year, m)[1] for m in range(1, 13))

        return {
            "success": True,
            "year": year,
            "total_inks": len(inks),
            "total_days_in_year": total_days,
            "total_assigned_days": total_assigned,
            "total_unassigned_days": total_days - total_assigned,
            "monthly_summary": monthly_summary
        }

    def find_available_inks_for_theme(
        query: Optional[str] = None,
        color: Optional[str] = None,
        brand: Optional[str] = None,
        include_session_assigned: bool = True,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Find inks that could fill gaps in the schedule or be reshuffled for better organization.

        Use this tool after moving inks to find candidates for backfilling empty slots.
        Returns both unassigned inks AND session-assigned inks (which can be moved).
        API-assigned inks are never returned since they cannot be moved.

        Args:
            query: Optional text to search in ink names or properties (e.g., "shimmer", "sheen")
            color: Optional color tag to filter by (e.g., "blue", "green", "red")
            brand: Optional brand name to filter by
            include_session_assigned: If True (default), include inks with session assignments
                                      that could be reshuffled. If False, only unassigned inks.
            limit: Maximum number of results to return (default 20)

        Returns:
            List of available inks with their current assignment status:
            - "unassigned": Not assigned anywhere, ready to use
            - "session_assigned": Assigned by you this session, can be moved if reshuffling improves the schedule
        """
        inks = _snapshot["inks"]

        if not inks:
            return {"success": False, "message": "No inks available in collection"}

        api = _snapshot["api"]
        session = _snapshot["session"]

        # Build reverse lookups: ink_idx -> date
        api_assigned_indices = set(api.values())
        session_idx_to_date = {idx: date for date, idx in session.items()}

        def matches_filters(ink: dict) -> bool:
            """Check if ink matches all provided filters."""
            if query:
                query_lower = query.lower()
                name_match = query_lower in ink.get("name", "").lower()
                brand_match = query_lower in ink.get("brand_name", "").lower()
                tags = ink.get("cluster_tags", [])
                tag_match = any(query_lower in tag.lower() for tag in tags)
                comment = ink.get("private_comment", "")
                comment_match = query_lower in comment.lower() if comment else False

                if not (name_match or brand_match or tag_match or comment_match):
                    return False

            if color:
                tags = ink.get("cluster_tags", [])
                if not any(color.lower() in tag.lower() for tag in tags):
                    return False

            if brand:
                if brand.lower() not in ink.get("brand_name", "").lower():
                    return False

            return True

        available_inks = []
        counts = {"unassigned": 0, "session_assigned": 0, "api_assigned": 0}

        for idx, ink in enumerate(inks):
            # Categorize the ink
            if idx in api_assigned_indices:
                counts["api_assigned"] += 1
                continue  # Never include API-assigned inks

            if idx in session_idx_to_date:
                counts["session_assigned"] += 1
                if not include_session_assigned:
                    continue
                status = "session_assigned"
                current_date = session_idx_to_date[idx]
            else:
                counts["unassigned"] += 1
                status = "unassigned"
                current_date = None

            if not matches_filters(ink):
                continue

            ink_info = extract_ink_info(ink, idx)
            ink_info["status"] = status
            if current_date:
                ink_info["current_date"] = current_date

            available_inks.append(ink_info)

            if len(available_inks) >= limit:
                break

        return {
            "success": True,
            "collection_summary": {
                "total_inks": len(inks),
                "unassigned": counts["unassigned"],
                "session_assigned": counts["session_assigned"],
                "api_assigned_immovable": counts["api_assigned"]
            },
            "matches_returned": len(available_inks),
            "filters_applied": {
                "query": query,
                "color": color,
                "brand": brand,
                "include_session_assigned": include_session_assigned
            },
            "available_inks": available_inks,
            "hint": "Unassigned inks can be directly assigned. Session-assigned inks can be moved to improve the overall schedule."
        }

    def set_month_theme(month: int, theme: str, description: str = "",
                        year: Optional[int] = None) -> Dict[str, Any]:
        """
        Set a theme name and description for a specific month.

        Use this after assigning inks to a month to give it a cohesive theme name
        that describes the collection of inks assigned to that month.

        Args:
            month: Month number (1-12)
            theme: Short theme name (e.g., "Winter Blues", "Autumn Warmth")
            description: Longer description of the theme (e.g., "Cool tones to match the winter sky")
            year: Year (defaults to currently selected year)

        Returns:
            Success status and the saved theme information.
        """
        if session_themes_reactive is None:
            return {"success": False, "message": "Theme storage not available"}

        if year is None:
            year = _snapshot["year"]

        if not 1 <= month <= 12:
            return {"success": False, "message": f"Invalid month: {month}. Must be 1-12."}

        if not theme or not theme.strip():
            return {"success": False, "message": "Theme name cannot be empty"}

        month_key = f"{year}-{month:02d}"
        themes = _snapshot["themes"].copy()
        themes[month_key] = {
            "theme": theme.strip(),
            "description": description.strip() if description else ""
        }
        session_themes_reactive.set(themes)
        _snapshot["themes"] = themes.copy()

        return {
            "success": True,
            "message": f"Set theme for {calendar.month_name[month]} {year}",
            "month": month,
            "month_name": calendar.month_name[month],
            "year": year,
            "theme": theme.strip(),
            "description": description.strip() if description else "",
            "note": "Theme saved to session. Use Save Session to persist."
        }

    def get_month_theme(month: int, year: Optional[int] = None) -> Dict[str, Any]:
        """
        Get the theme for a specific month.

        Args:
            month: Month number (1-12)
            year: Year (defaults to currently selected year)

        Returns:
            Theme information if set, or indication that no theme exists.
        """
        if year is None:
            year = _snapshot["year"]

        if not 1 <= month <= 12:
            return {"success": False, "message": f"Invalid month: {month}. Must be 1-12."}

        month_key = f"{year}-{month:02d}"

        # Check session themes first
        themes = _snapshot["themes"]
        if month_key in themes:
                theme_data = themes[month_key]
                return {
                    "success": True,
                    "month": month,
                    "month_name": calendar.month_name[month],
                    "year": year,
                    "theme": theme_data.get("theme", ""),
                    "description": theme_data.get("description", ""),
                    "source": "session"
                }

        return {
            "success": True,
            "month": month,
            "month_name": calendar.month_name[month],
            "year": year,
            "theme": None,
            "description": None,
            "message": "No theme set for this month"
        }

    def clear_month_theme(month: int, year: Optional[int] = None) -> Dict[str, Any]:
        """
        Remove the theme for a specific month.

        Args:
            month: Month number (1-12)
            year: Year (defaults to currently selected year)

        Returns:
            Success status.
        """
        if session_themes_reactive is None:
            return {"success": False, "message": "Theme storage not available"}

        if year is None:
            year = _snapshot["year"]

        if not 1 <= month <= 12:
            return {"success": False, "message": f"Invalid month: {month}. Must be 1-12."}

        month_key = f"{year}-{month:02d}"
        themes = _snapshot["themes"].copy()

        if month_key not in themes:
            return {
                "success": True,
                "message": f"No theme was set for {calendar.month_name[month]} {year}",
                "month": month,
                "year": year
            }

        del themes[month_key]
        session_themes_reactive.set(themes)
        _snapshot["themes"] = themes.copy()

        return {
            "success": True,
            "message": f"Cleared theme for {calendar.month_name[month]} {year}",
            "month": month,
            "month_name": calendar.month_name[month],
            "year": year
        }

    # Return tool functions AND the snapshot updater
    tools = [
        list_all_inks,
        search_inks,
        get_month_assignments,
        assign_ink_to_date,
        bulk_assign_month,
        unassign_ink_from_date,
        clear_month_assignments,
        get_current_assignments_summary,
        find_available_inks_for_theme,
        set_month_theme,
        get_month_theme,
        clear_month_theme
    ]
    return tools, update_snapshot
