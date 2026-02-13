"""
Tool functions for LLM chat to interact with ink assignments.

These are thin wrappers around assignment_logic.py functions that:
- Bind to reactive state (ink_data, session_assignments, api_assignments)
- Handle reactive updates to session state
- Format responses for the LLM

Session assignments are experimental and not auto-persisted.
API assignments (from ink_cache) are protected and read-only.
"""
from typing import List, Dict, Optional, Any
import calendar

from assignment_logic import (
    find_ink_by_name,
    search_inks as search_inks_pure,
    move_ink_assignment,
)


def create_tool_functions(ink_data_reactive, selected_year_reactive,
                          session_assignments_reactive, api_assignments_reactive):
    """
    Create tool functions bound to reactive state.

    Args:
        ink_data_reactive: Reactive value containing list of inks
        selected_year_reactive: Reactive value containing selected year
        session_assignments_reactive: Reactive value for session assignments {date: ink_idx}
        api_assignments_reactive: Reactive value for API assignments {date: ink_idx} (read-only)

    Returns:
        List of tool functions ready to register with chatlas
    """

    def _get_merged_assignments():
        """Get merged view of API + session assignments. API takes precedence."""
        api = api_assignments_reactive.get()
        session = session_assignments_reactive.get()
        return {**session, **api}

    def list_all_inks() -> Dict[str, Any]:
        """
        List all inks in the collection with their basic information.

        Returns a summary of all available inks including brand, name, color tags,
        and whether they're already assigned for the current year.
        """
        inks = ink_data_reactive.get()

        if not inks:
            return {"success": False, "message": "No inks available in collection"}

        merged = _get_merged_assignments()
        assigned_indices = set(merged.values())

        ink_list = []
        for idx, ink in enumerate(inks):
            ink_list.append({
                "index": idx,
                "brand": ink.get("brand_name", "Unknown"),
                "name": ink.get("name", "Unknown"),
                "color_tags": ink.get("cluster_tags", []),
                "already_assigned": idx in assigned_indices
            })

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
        inks = ink_data_reactive.get()
        year = selected_year_reactive.get()

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
            year = selected_year_reactive.get()

        if not 1 <= month <= 12:
            return {"success": False, "message": f"Invalid month: {month}. Must be 1-12."}

        inks = ink_data_reactive.get()
        if not inks:
            return {"success": False, "message": "No inks available in collection"}

        merged = _get_merged_assignments()
        api = api_assignments_reactive.get()
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
        inks = ink_data_reactive.get()

        if not inks:
            return {"success": False, "message": "No inks available in collection"}

        # Find the ink first
        result = find_ink_by_name(ink_identifier, inks)
        if not result:
            return {"success": False, "message": f"Could not find ink matching '{ink_identifier}'."}

        idx, ink = result

        # Use unified move function (assign = move with from_date=None)
        session = session_assignments_reactive.get()
        api = api_assignments_reactive.get()

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

        # Update reactive state
        session_assignments_reactive.set(new_session)

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
            year = selected_year_reactive.get()

        if not 1 <= month <= 12:
            return {"success": False, "message": f"Invalid month: {month}. Must be 1-12."}

        inks = ink_data_reactive.get()
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
        session = session_assignments_reactive.get().copy()
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
            session=session_assignments_reactive.get(),
            api=api_assignments_reactive.get(),
            from_date=date_str,
            to_date=None,
            inks=ink_data_reactive.get()
        )

        if not move_result.success:
            return move_result.to_dict()

        # Update reactive state
        session_assignments_reactive.set(new_session)

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
            year = selected_year_reactive.get()

        if not 1 <= month <= 12:
            return {"success": False, "message": f"Invalid month: {month}. Must be 1-12."}

        inks = ink_data_reactive.get()
        session = session_assignments_reactive.get()
        api = api_assignments_reactive.get()

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
            year = selected_year_reactive.get()

        inks = ink_data_reactive.get()
        if not inks:
            return {"success": False, "message": "No inks available in collection"}

        merged = _get_merged_assignments()
        api = api_assignments_reactive.get()

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

    return [
        list_all_inks,
        search_inks,
        get_month_assignments,
        assign_ink_to_date,
        bulk_assign_month,
        unassign_ink_from_date,
        clear_month_assignments,
        get_current_assignments_summary
    ]
