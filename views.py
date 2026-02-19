"""
View rendering functions for the ink scheduler app.

These functions take data as parameters and return Shiny UI elements.
They contain no reactive logic - that stays in app.py.
"""
from datetime import datetime
from calendar import monthrange
from shiny import ui

from app_helpers import get_month_dates, make_button_id, prepare_month_cells


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
        daily_assignments: Merged assignments {date_str: ink_idx}
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
        ink_idx = daily_assignments.get(date_str)

        if ink_idx is not None and ink_idx < len(inks):
            ink = inks[ink_idx]
            cell_content = _render_calendar_cell_with_ink(
                date_str, day, ink, ink_idx,
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
    ink_idx: int,
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

    cell_components = [
        ui.div(
            ui.strong(str(day), class_="calendar-day-number"),
            ui.div(ink_swatch_fn(ink_color, "lg")),
            class_="calendar-cell-header"
        ),
        ui.span(brand, class_="calendar-brand"),
        ui.span(ink_name, class_="calendar-ink-name")
    ]

    main_content = ui.div(*cell_components, class_="calendar-cell-content")

    # Build data attributes for drag-and-drop
    data_attrs = {
        "data-date": date_str,
        "data-ink-idx": str(ink_idx),
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
        daily_assignments: Merged assignments {date_str: ink_idx}
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
        ink_idx = daily_assignments.get(date_str)

        date_col = ui.div(
            ui.strong(date_obj.strftime("%a, %b %d")),
            class_="list-date-col"
        )

        if ink_idx is not None and ink_idx < len(inks):
            row = _render_list_row_with_ink(
                date_str, date_obj, date_col,
                inks[ink_idx], ink_idx,
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
    ink_idx: int,
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
        action_col = ui.div(
            ui.span(date_obj.strftime("%b %d, %Y"), class_="api-date-display"),
            ui.span("swatched", class_="api-badge"),
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
    ink_swatch_fn
):
    """
    Render the ink collection view with search and inline assignment.

    Args:
        inks: List of ink dictionaries
        daily_assignments: Merged assignments {date_str: ink_idx}
        session_assignments: Session-only assignments
        api_assignments: API assignments (protected)
        year: Year for assignments
        search_query: Search filter string
        ink_swatch_fn: Function to render ink swatch SVG

    Returns:
        Shiny UI element with ink collection table
    """
    if not inks:
        return ui.p("No inks loaded. Please fetch your collection first.")

    # Build reverse lookup: ink_idx -> assigned_date
    ink_to_date = {idx: date_str for date_str, idx in daily_assignments.items()}

    # Filter inks by search query
    query_lower = search_query.lower() if search_query else ""
    filtered_indices = []
    for idx, ink in enumerate(inks):
        if query_lower:
            name = ink.get("name", "").lower()
            brand = ink.get("brand_name", "").lower()
            if query_lower not in name and query_lower not in brand:
                continue
        filtered_indices.append(idx)

    # Table header
    header_row = ui.div(
        ui.div("Color", class_="ink-col-color"),
        ui.div("Brand", class_="ink-col-brand"),
        ui.div("Name", class_="ink-col-name"),
        ui.div("Assignment", class_="ink-col-assignment"),
        class_="ink-header-row"
    )

    rows = []
    for idx in filtered_indices:
        ink = inks[idx]
        current_date = ink_to_date.get(idx)
        is_api_assigned = current_date and current_date in api_assignments

        row = _render_ink_collection_row(
            idx, ink, current_date, is_api_assigned,
            session_assignments, api_assignments,
            ink_swatch_fn
        )
        rows.append(row)

    if not rows:
        rows = [ui.div(ui.p("No inks match your search."), class_="ink-no-results")]

    table_content = ui.div(*rows, class_="ink-table-content")
    return ui.div(header_row, table_content, class_="ink-collection-table")


def _render_ink_collection_row(
    idx: int,
    ink: dict,
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
    name_col = ui.div(name, class_="ink-name-col")

    # Assignment column
    if is_api_assigned:
        # API assigned - show as read-only
        date_obj = datetime.strptime(current_date, "%Y-%m-%d")
        assignment_col = ui.div(
            ui.span(date_obj.strftime("%b %d"), class_="api-date-display"),
            ui.span("swatched", class_="api-badge"),
            class_="ink-assignment-col"
        )
        row_class = "ink-row ink-row-api"
    elif current_date:
        # Session assigned - editable
        date_obj = datetime.strptime(current_date, "%Y-%m-%d")
        assignment_col = ui.div(
            ui.input_date(f"ink_date_{idx}", "", value=date_obj.date()),
            ui.input_action_button(
                f"ink_save_{idx}",
                "Save",
                class_="btn-sm btn-outline-success"
            ),
            ui.input_action_button(
                f"ink_remove_{idx}",
                "✕",
                class_="btn-sm btn-outline-danger ink-remove-btn"
            ),
            class_="ink-assignment-col"
        )
        row_class = "ink-row ink-row-session"
    else:
        # Unassigned - show date picker
        assignment_col = ui.div(
            ui.input_date(f"ink_date_{idx}", "", value=None),
            class_="ink-assignment-col"
        )
        row_class = "ink-row"

    return ui.div(
        color_col,
        brand_col,
        name_col,
        assignment_col,
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
