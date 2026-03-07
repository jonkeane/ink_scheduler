"""
View rendering functions for the ink scheduler app.

These functions take data as parameters and return Shiny UI elements.
They contain no reactive logic - that stays in app.py.
"""
from datetime import datetime
from calendar import monthrange
from shiny import ui

from app_helpers import get_month_dates, make_button_id, prepare_month_cells
from assignment_logic import find_ink_by_macro_cluster_id, normalize_apostrophes, parse_ink_identifier


# =============================================================================
# SVG Icons (extracted as constants)
# =============================================================================

SAVE_ICON_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
    <polyline points="17 21 17 13 7 13 7 21"/>
    <polyline points="7 3 7 8 15 8"/>
</svg>'''

INK_BOTTLE_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#666" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M10 2h4v2h-4z"/>
    <path d="M8 4h8l1 4H7l1-4z"/>
    <path d="M7 8h10v12a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2V8z"/>
    <path d="M9 13h6v5H9z" fill="#666" opacity="0.3"/>
</svg>'''

# Trash icon for deleting API assignments (distinct from session remove)
TRASH_ICON_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <polyline points="3 6 5 6 21 6"/>
    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
    <line x1="10" y1="11" x2="10" y2="17"/>
    <line x1="14" y1="11" x2="14" y2="17"/>
</svg>'''

# External link icon for FPC cluster page
FPC_LINK_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
    <polyline points="15 3 21 3 21 9"/>
    <line x1="10" y1="14" x2="21" y2="3"/>
</svg>'''

# FPC base URL for cluster pages
FPC_CLUSTER_URL = "https://www.fountainpencompanion.com/inks"


# =============================================================================
# Calendar View
# =============================================================================

def render_calendar_view(
    inks: list[dict],
    daily_assignments: dict,
    session_assignments: dict,
    api_assignments: dict,
    year: int,
    month: int,
    ink_swatch_fn
):
    """
    Render the calendar grid view.

    Args:
        inks: List of ink dictionaries
        daily_assignments: Merged assignments {date_str: macro_cluster_id}
        session_assignments: Session-only assignments
        api_assignments: API assignments (protected)
        year: Year to display
        month: Month to display (1-12)
        ink_swatch_fn: Function to render ink swatch SVG

    Returns:
        Shiny UI element with calendar grid
    """
    if not inks:
        return ui.p("No inks loaded. Please fetch your collection first.")

    num_days = monthrange(year, month)[1]
    first_weekday = datetime(year, month, 1).weekday()

    # Build calendar grid
    weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    # Header row
    header = ui.div(
        *[ui.div(day, class_="calendar-weekday") for day in weekdays],
        class_="calendar-header"
    )

    # Calendar days - empty divs for grid cells before first day
    cells = [ui.div(class_="calendar-cell-empty") for _ in range(first_weekday)]

    for day in range(1, num_days + 1):
        date_str = f"{year}-{month:02d}-{day:02d}"
        macro_cluster_id = daily_assignments.get(date_str)

        result = find_ink_by_macro_cluster_id(macro_cluster_id, inks) if macro_cluster_id else None
        if result:
            ink_idx, ink = result
            cell_content = _render_calendar_cell_with_ink(
                date_str, day, ink, macro_cluster_id,
                session_assignments, api_assignments,
                ink_swatch_fn
            )
        else:
            # Empty cell - can be a drop target
            cell_content = ui.div(
                ui.strong(str(day)),
                class_="calendar-cell calendar-drop-target",
                **{"data-date": date_str}
            )

        cells.append(cell_content)

    # Fill remaining cells with empty divs
    while len(cells) % 7 != 0:
        cells.append(ui.div(class_="calendar-cell-empty"))

    calendar_grid = ui.div(*cells, class_="calendar-grid")

    return ui.div(header, calendar_grid)


def _render_calendar_cell_with_ink(
    date_str: str,
    day: int,
    ink: dict,
    macro_cluster_id: str,
    session_assignments: dict,
    api_assignments: dict,
    ink_swatch_fn
):
    """Render a calendar cell that has an ink assigned."""
    ink_name = ink.get("name", "Unknown")
    brand = ink.get("brand_name", "")
    ink_color = ink.get("color", "#cccccc")

    is_session = date_str in session_assignments and date_str not in api_assignments
    is_protected = date_str in api_assignments

    # Build ink name element with optional FPC link (only for macro: identifiers)
    id_type, id_value = parse_ink_identifier(macro_cluster_id) if macro_cluster_id else ("", "")
    if id_type == "macro" and id_value:
        fpc_link_icon = ui.HTML(FPC_LINK_SVG)
        fpc_url = f"{FPC_CLUSTER_URL}/{id_value}"
        ink_name_element = ui.span(
            ui.span(ink_name),
            ui.tags.a(
                fpc_link_icon,
                href=fpc_url,
                target="_blank",
                class_="calendar-fpc-link",
                title="View on Fountain Pen Companion"
            ),
            class_="calendar-ink-name"
        )
    else:
        ink_name_element = ui.span(ink_name, class_="calendar-ink-name")

    cell_components = [
        ui.div(
            ui.strong(str(day), class_="calendar-day-number"),
            ui.div(ink_swatch_fn(ink_color, "lg")),
            class_="calendar-cell-header"
        ),
        ui.span(brand, class_="calendar-brand"),
        ink_name_element
    ]

    main_content = ui.div(*cell_components, class_="calendar-cell-content")

    # Build data attributes for drag-and-drop
    data_attrs = {
        "data-date": date_str,
        "data-macro-cluster-id": macro_cluster_id,
    }
    if is_protected:
        data_attrs["data-protected"] = "true"

    # Determine CSS classes
    css_classes = "calendar-cell-assigned calendar-drop-target"
    if is_session:
        css_classes += " calendar-draggable"

    if is_session:
        save_icon = ui.HTML(SAVE_ICON_SVG)
        save_btn = ui.input_action_button(
            make_button_id("save", date_str),
            save_icon,
            class_="btn-sm calendar-save-btn"
        )
        remove_btn = ui.input_action_button(
            make_button_id("remove", date_str),
            "✕",
            class_="btn-sm calendar-remove-btn"
        )
        return ui.div(
            save_btn,
            remove_btn,
            main_content,
            class_=css_classes,
            draggable="true",
            **data_attrs
        )
    else:
        return ui.div(
            main_content,
            class_=css_classes,
            **data_attrs
        )


# =============================================================================
# List View
# =============================================================================

def render_list_view(
    inks: list[dict],
    daily_assignments: dict,
    session_assignments: dict,
    api_assignments: dict,
    year: int,
    month: int,
    ink_swatch_fn
):
    """
    Render the list view.

    Args:
        inks: List of ink dictionaries
        daily_assignments: Merged assignments {date_str: macro_cluster_id}
        session_assignments: Session-only assignments
        api_assignments: API assignments (protected)
        year: Year to display
        month: Month to display (1-12)
        ink_swatch_fn: Function to render ink swatch SVG

    Returns:
        Shiny UI element with list view
    """
    if not inks:
        return ui.p("No inks loaded. Please fetch your collection first.")

    # Table header
    header_row = ui.div(
        ui.div("Date", class_="list-col-date"),
        ui.div("Color", class_="list-col-color"),
        ui.div("Brand", class_="list-col-brand"),
        ui.div("Name", class_="list-col-name"),
        ui.div("Actions", class_="list-col-actions"),
        class_="list-header-row"
    )

    rows = []
    num_days = monthrange(year, month)[1]

    for day in range(1, num_days + 1):
        date_str = f"{year}-{month:02d}-{day:02d}"
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        macro_cluster_id = daily_assignments.get(date_str)

        date_col = ui.div(
            ui.strong(date_obj.strftime("%a, %b %d")),
            class_="list-date-col"
        )

        result = find_ink_by_macro_cluster_id(macro_cluster_id, inks) if macro_cluster_id else None
        if result:
            _, ink = result
            row = _render_list_row_with_ink(
                date_str, date_obj, date_col,
                ink, macro_cluster_id,
                session_assignments, api_assignments,
                ink_swatch_fn
            )
        else:
            row = _render_list_row_unassigned(date_str, date_col)

        rows.append(row)

    list_content = ui.div(*rows, class_="list-content")
    return ui.div(header_row, list_content)


def _render_list_row_with_ink(
    date_str: str,
    date_obj,
    date_col,
    ink: dict,
    macro_cluster_id: str,
    session_assignments: dict,
    api_assignments: dict,
    ink_swatch_fn
):
    """Render a list row that has an ink assigned."""
    color = ink.get("color", "#888888")
    brand = ink.get("brand_name", "Unknown")
    name = ink.get("name", "Unknown")

    can_edit = date_str in session_assignments and date_str not in api_assignments
    is_api = date_str in api_assignments

    swatch = ink_swatch_fn(color, "sm")
    brand_col = ui.div(brand, class_="list-brand-col")

    # Build name column with optional FPC link (only for macro: identifiers)
    id_type, id_value = parse_ink_identifier(macro_cluster_id) if macro_cluster_id else ("", "")
    if id_type == "macro" and id_value:
        fpc_link_icon = ui.HTML(FPC_LINK_SVG)
        fpc_url = f"{FPC_CLUSTER_URL}/{id_value}"
        name_col = ui.div(
            ui.span(name),
            ui.tags.a(
                fpc_link_icon,
                href=fpc_url,
                target="_blank",
                class_="list-fpc-link",
                title="View on Fountain Pen Companion"
            ),
            class_="list-name-col"
        )
    else:
        name_col = ui.div(name, class_="list-name-col")

    if can_edit:
        action_components = [
            ui.div(
                ui.input_date(make_button_id("date", date_str), "", value=date_obj.date()),
                class_="calendar-icon-picker"
            ),
            ui.input_action_button(
                make_button_id("save", date_str),
                "Save",
                class_="btn-sm btn-outline-success list-save-btn"
            ),
            ui.input_action_button(
                make_button_id("remove", date_str),
                "Remove",
                class_="btn-sm btn-outline-danger list-remove-btn"
            )
        ]
        action_col = ui.div(*action_components, class_="list-actions-col")
    elif is_api:
        trash_icon = ui.HTML(TRASH_ICON_SVG)
        action_col = ui.div(
            ui.span(date_obj.strftime("%b %d, %Y"), class_="api-date-display"),
            ui.span("swatched", class_="api-badge"),
            ui.input_action_button(
                make_button_id("api_delete", date_str),
                trash_icon,
                class_="btn-sm btn-outline-danger list-api-delete-btn",
                title="Delete API assignment"
            ),
            class_="list-actions-col"
        )
    else:
        action_col = ui.div()

    return ui.div(
        date_col,
        ui.div(swatch, class_="list-swatch-col"),
        brand_col,
        name_col,
        action_col,
        class_="list-row"
    )


def _render_list_row_unassigned(date_str: str, date_col):
    """Render a list row with no ink assigned."""
    ink_bottle_svg = ui.HTML(INK_BOTTLE_SVG)

    assign_button = ui.input_action_button(
        make_button_id("assign", date_str),
        ink_bottle_svg,
        class_="ink-assign-btn",
        title="Assign ink to this date"
    )

    return ui.div(
        date_col,
        ui.div(class_="list-swatch-col"),
        ui.div(class_="list-brand-col"),
        ui.div(
            ui.span("Unassigned", class_="list-unassigned-text"),
            class_="list-unassigned-name-col"
        ),
        ui.div(assign_button, class_="list-actions-col"),
        class_="list-row-unassigned"
    )


# =============================================================================
# Ink Collection View
# =============================================================================

def render_ink_collection_view(
    inks: list[dict],
    daily_assignments: dict,
    session_assignments: dict,
    api_assignments: dict,
    year: int,
    search_query: str,
    status_filter: list[str],
    ink_swatch_fn,
    sort_field: str = "brand",
    sort_direction: str = "asc"
):
    """
    Render the ink collection view with search and inline assignment.

    Args:
        inks: List of ink dictionaries
        daily_assignments: Merged assignments {date_str: macro_cluster_id}
        session_assignments: Session-only assignments
        api_assignments: API assignments (protected)
        year: Year for assignments
        search_query: Search filter string
        status_filter: List of statuses to show: "unassigned", "session", "api"
        ink_swatch_fn: Function to render ink swatch SVG
        sort_field: Field to sort by ("color", "brand", "name", "date")
        sort_direction: Sort direction ("asc" or "desc")

    Returns:
        Shiny UI element with ink collection table
    """
    if not inks:
        return ui.p("No inks loaded. Please fetch your collection first.")

    # Build reverse lookup: macro_cluster_id -> assigned_date
    macro_id_to_date = {macro_id: date_str for date_str, macro_id in daily_assignments.items()}

    # Build session macro_id lookup (session-only, not API)
    session_macro_ids = set()
    for date_str, macro_id in session_assignments.items():
        if date_str not in api_assignments:
            session_macro_ids.add(macro_id)

    # Filter inks by search query and status
    # Normalize apostrophes for consistency with LLM-generated queries
    query_lower = normalize_apostrophes(search_query).lower() if search_query else ""
    filtered_indices = []
    for idx, ink in enumerate(inks):
        # Search filter
        if query_lower:
            name = normalize_apostrophes(ink.get("name", "")).lower()
            brand = normalize_apostrophes(ink.get("brand_name", "")).lower()
            if query_lower not in name and query_lower not in brand:
                continue

        # Status filter - determine ink's status
        if ink.get("macro_cluster_id"):
            ink_identifier = f"macro:{ink['macro_cluster_id']}"
        else:
            ink_identifier = f"id:{ink.get('id', '')}"

        current_date = macro_id_to_date.get(ink_identifier)
        is_session = ink_identifier in session_macro_ids
        is_api = current_date and current_date in api_assignments

        # Determine status category
        if is_api:
            status = "api"
        elif is_session:
            status = "session"
        else:
            status = "unassigned"

        # Apply status filter
        if status not in status_filter:
            continue

        filtered_indices.append(idx)

    # Sort filtered indices
    def get_sort_key(idx: int):
        ink = inks[idx]
        if sort_field == "color":
            # Sort by hex color value
            return ink.get("color", "#ffffff").lower()
        elif sort_field == "brand":
            return ink.get("brand_name", "").lower()
        elif sort_field == "name":
            return ink.get("name", "").lower()
        elif sort_field == "date":
            # Get assigned date for this ink
            if ink.get("macro_cluster_id"):
                ink_id = f"macro:{ink['macro_cluster_id']}"
            else:
                ink_id = f"id:{ink.get('id', '')}"
            assigned_date = macro_id_to_date.get(ink_id, "")
            # Unassigned inks sort last (or first if desc)
            return assigned_date if assigned_date else ("9999" if sort_direction == "asc" else "0000")
        return ""

    filtered_indices.sort(key=get_sort_key, reverse=(sort_direction == "desc"))

    # Table header with sortable columns
    def sort_indicator(field: str) -> str:
        if sort_field != field:
            return ""  # Hide arrow when not active
        return " \u25B2" if sort_direction == "asc" else " \u25BC"

    header_row = ui.div(
        ui.input_action_button(
            "sort_color", f"Color{sort_indicator('color')}",
            class_="ink-col-color ink-sort-header"
        ),
        ui.input_action_button(
            "sort_brand", f"Brand{sort_indicator('brand')}",
            class_="ink-col-brand ink-sort-header"
        ),
        ui.input_action_button(
            "sort_name", f"Name{sort_indicator('name')}",
            class_="ink-col-name ink-sort-header"
        ),
        ui.div("Actions", class_="ink-col-actions"),
        ui.input_action_button(
            "sort_date", f"Date{sort_indicator('date')}",
            class_="ink-col-date ink-sort-header"
        ),
        class_="ink-header-row"
    )

    rows = []
    for idx in filtered_indices:
        ink = inks[idx]
        if ink.get("macro_cluster_id"):
            ink_identifier = f"macro:{ink['macro_cluster_id']}"
        else:
            ink_identifier = f"id:{ink.get('id', '')}"
        current_date = macro_id_to_date.get(ink_identifier)
        is_api_assigned = current_date and current_date in api_assignments

        row = _render_ink_collection_row(
            idx, ink, ink_identifier, current_date, is_api_assigned,
            session_assignments, api_assignments,
            ink_swatch_fn
        )
        rows.append(row)

    if not rows:
        rows = [ui.div(ui.p("No inks match your filters."), class_="ink-no-results")]

    table_content = ui.div(*rows, class_="ink-table-content")
    return ui.div(header_row, table_content, class_="ink-collection-table")


def _render_ink_collection_row(
    idx: int,
    ink: dict,
    macro_cluster_id: str,
    current_date: str,
    is_api_assigned: bool,
    session_assignments: dict,
    api_assignments: dict,
    ink_swatch_fn
):
    """Render a single row in the ink collection table."""
    color = ink.get("color", "#888888")
    brand = ink.get("brand_name", "Unknown")
    name = ink.get("name", "Unknown")

    swatch = ink_swatch_fn(color, "sm")

    # Color and info columns
    color_col = ui.div(swatch, class_="ink-swatch-col")
    brand_col = ui.div(brand, class_="ink-brand-col")

    # Name column - include swatched badge if API assigned
    if is_api_assigned:
        name_col = ui.div(
            ui.span(name, class_="ink-name-text"),
            ui.span("swatched", class_="api-badge"),
            class_="ink-name-col"
        )
    else:
        name_col = ui.div(name, class_="ink-name-col")

    # Actions and Date columns
    if is_api_assigned:
        # API assigned - trash button only
        date_obj = datetime.strptime(current_date, "%Y-%m-%d")
        trash_icon = ui.HTML(TRASH_ICON_SVG)
        actions_col = ui.div(
            ui.input_action_button(
                f"ink_api_delete_{idx}",
                trash_icon,
                class_="btn-sm btn-outline-danger ink-action-btn",
                title="Remove from API"
            ),
            class_="ink-actions-col"
        )
        date_col = ui.div(
            ui.span(date_obj.strftime("%b %d, %Y"), class_="ink-date-display"),
            class_="ink-date-col"
        )
        row_class = "ink-row ink-row-api"
    elif current_date:
        # Session assigned - assign/unassign buttons
        date_obj = datetime.strptime(current_date, "%Y-%m-%d")
        actions_col = ui.div(
            ui.input_action_button(
                f"ink_save_{idx}",
                "assign",
                class_="btn-sm btn-outline-success ink-action-btn",
                title="Save assignment to API"
            ),
            ui.input_action_button(
                f"ink_remove_{idx}",
                "unassign",
                class_="btn-sm btn-outline-secondary ink-action-btn",
                title="Clear assignment"
            ),
            class_="ink-actions-col"
        )
        date_col = ui.div(
            ui.input_date(f"ink_date_{idx}", "", value=date_obj.date()),
            class_="ink-date-col"
        )
        row_class = "ink-row ink-row-session"
    else:
        # Unassigned - empty actions, date picker
        actions_col = ui.div(class_="ink-actions-col")
        date_col = ui.div(
            ui.input_date(f"ink_date_{idx}", "", value=""),
            class_="ink-date-col"
        )
        row_class = "ink-row"

    return ui.div(
        color_col,
        brand_col,
        name_col,
        actions_col,
        date_col,
        class_=row_class
    )


# =============================================================================
# Month Assignment Summary
# =============================================================================

def render_month_assignment_summary(
    inks: list[dict],
    daily_assignments: dict,
    year: int
):
    """
    Render the month-by-month assignment summary table.

    Args:
        inks: List of ink dictionaries
        daily_assignments: All assignments {date_str: ink_idx}
        year: Year to summarize

    Returns:
        Shiny UI element with summary table
    """
    from assignment_logic import get_month_summary

    if not inks:
        return ui.p("No inks loaded.")

    # Table header
    header = ui.div(
        ui.div("Month", class_="summary-col-month"),
        ui.div("Assigned", class_="summary-col-count"),
        ui.div("Total Days", class_="summary-col-total"),
        ui.div("Coverage", class_="summary-col-coverage"),
        class_="summary-header-row"
    )

    rows = []
    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]

    for month_num in range(1, 13):
        # get_month_summary returns list of ink indices for that month
        ink_indices = get_month_summary(daily_assignments, year, month_num)
        assigned = len(ink_indices)
        total = monthrange(year, month_num)[1]
        coverage = f"{(assigned / total * 100):.0f}%" if total > 0 else "0%"

        row = ui.div(
            ui.div(month_names[month_num - 1], class_="summary-month-col"),
            ui.div(str(assigned), class_="summary-count-col"),
            ui.div(str(total), class_="summary-total-col"),
            ui.div(coverage, class_="summary-coverage-col"),
            class_="summary-row"
        )
        rows.append(row)

    table_content = ui.div(*rows, class_="summary-content")
    return ui.div(header, table_content, class_="summary-table")
