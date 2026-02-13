from shiny import App, ui, render, reactive
from datetime import datetime
import pandas as pd
from calendar import monthrange
import os
import logging

# Configure chatlas logging before importing chatlas-related modules
os.environ["CHATLAS_LOG"] = "debug"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

from dotenv import load_dotenv
from assignment_logic import (
    create_explicit_assignments_only,
    get_month_summary,
    parse_theme_from_comment,
    move_ink_assignment,
)
from api_client import fetch_all_collected_inks
from llm_organizer import create_llm_chat, format_all_inks_for_llm
from ink_cache import save_inks_to_cache, load_inks_from_cache, get_cache_info
from chat_tools import create_tool_functions
import traceback

# Load environment variables from .env file
load_dotenv()

# Get API token from environment (if available)
DEFAULT_API_TOKEN = os.getenv("FPC_API_TOKEN", "")

app_ui = ui.page_fluid(
    ui.include_css("styles.css"),

    ui.layout_sidebar(
        ui.sidebar(
            ui.input_action_button("fetch_inks", "Fetch My Inks", class_="btn-primary sidebar-btn-full"),
            ui.output_text("cache_status", inline=True),
            ui.h4("AI Organizer"),
            ui.chat_ui("ink_chat", height="400px"),
            ui.output_text("session_status", inline=True),
            ui.download_button("save_session", "Save Session", class_="btn-outline-secondary sidebar-btn-full"),
            ui.input_file("load_session", None, accept=[".json"], button_label="Load Session", multiple=False),
            ui.input_action_button("open_settings", "Settings", class_="btn-outline-secondary sidebar-btn-full"),
            width=400
        ),

        ui.div(
            ui.navset_tab(
            ui.nav_panel("Ink Calendar",
                ui.div(
                    ui.input_switch("view_mode", "List View", value=False, width="auto"),
                    ui.input_action_button("prev_month", "←", class_="btn-secondary btn-sm nav-btn-prev"),
                    ui.div(
                        ui.output_ui("month_label"),
                        ui.input_numeric("year", None, value=datetime.now().year,
                                       min=2020, max=2035, width="3rem"),
                        class_="month-year-container"
                    ),
                    ui.input_action_button("next_month", "→", class_="btn-secondary btn-sm"),
                    ui.output_ui("theme_label"),
                    class_="nav-controls"
                ),
                ui.output_ui("main_view")
            ),
            ui.nav_panel("Ink Collection",
                ui.input_text("ink_search", "Search inks:", placeholder="Type to filter by brand or name..."),
                ui.output_ui("ink_collection_view")
            ),
            ui.nav_panel("Month Assignment",
                ui.output_data_frame("month_assignment")
            ),
            id="main_tabs"
        ),
        ui.h2("Fountain Pen Ink Calendar", class_="page-title"),
        class_="tabs-header-row"
    )
    )
)

def ink_swatch_svg(color: str, size: str = "sm") -> ui.HTML:
    """Generate an SVG ink swatch with organic watercolor blob shape.

    Args:
        color: The ink color (hex or CSS color)
        size: "sm" for small (32x24), "lg" for large (80x50)
    """
    if size == "lg":
        # Large square-ish swatch for calendar view
        width, height = 80, 50
        viewbox = "0 0 100 90"
        path = """
            M 12 25
            C 5 22, 2 15, 8 8
            C 15 2, 28 0, 42 4
            C 52 1, 62 0, 75 5
            C 88 2, 96 10, 98 22
            C 100 35, 98 48, 95 60
            C 98 72, 94 82, 82 88
            C 70 92, 55 90, 42 86
            C 28 90, 15 88, 8 78
            C 2 68, 0 55, 4 42
            C 0 30, 5 22, 12 25
            Z
        """
    else:
        # Small swatch for list views
        width, height = 32, 24
        viewbox = "0 0 100 75"
        path = """
            M 15 20
            C 8 18, 5 12, 12 8
            C 18 4, 28 2, 38 5
            C 48 3, 55 1, 65 4
            C 75 2, 85 6, 92 12
            C 98 18, 100 28, 97 38
            C 100 48, 98 58, 92 65
            C 86 72, 75 75, 62 73
            C 50 76, 38 74, 28 70
            C 18 74, 8 70, 4 62
            C 0 54, 2 42, 5 32
            C 2 24, 6 18, 15 20
            Z
        """

    svg = f'''<svg width="{width}" height="{height}" viewBox="{viewbox}" xmlns="http://www.w3.org/2000/svg">
        <path fill="{color}" d="{path}"/>
    </svg>'''
    return ui.HTML(svg)

def server(input, output, session):
    # Reactive value for cache status
    cache_status = reactive.Value("No cache loaded")
    
    # Reactive value for current month (since we removed the input selector)
    current_month = reactive.Value(datetime.now().month)
    
    # Create Shiny chat interface (must be inside server function)
    chat = ui.Chat(id="ink_chat", messages=[])
    
    # Show settings modal when button is clicked
    @reactive.Effect
    @reactive.event(input.open_settings)
    def show_settings():
        m = ui.modal(
            ui.input_password("api_token", "API Token",
                            value=DEFAULT_API_TOKEN,
                            placeholder="Enter your API token"),
            ui.hr(),
            ui.input_select("llm_provider", "LLM Provider",
                          choices=["openai", "anthropic", "google"],
                          selected="openai"),
            ui.input_password("llm_api_key", "LLM API Key",
                            placeholder="Enter your LLM API key"),
            ui.input_action_button("clear_token", "Clear Token", class_="btn-secondary sidebar-btn-full clear-token"),
            title="Settings",
            easy_close=True,
            footer=ui.input_action_button("close_settings", "Save & Close", class_="btn-primary")
        )
        ui.modal_show(m)

    # Close settings modal when Save & Close is clicked
    @reactive.Effect
    @reactive.event(input.close_settings)
    def close_settings():
        ui.modal_remove()
        ui.notification_show("Settings saved", type="message", duration=2)
    
    # Reactive values to store data
    ink_data = reactive.Value([])
    api_assignments = reactive.Value({})  # Assignments from API cache (protected, read-only)
    session_assignments = reactive.Value({})  # Experimental assignments (editable, not auto-persisted)
    session_themes = reactive.Value({})  # Month themes {month_key: {theme, description}}
    llm_chat_instance = reactive.Value(None)  # Store LLM chat instance
    chat_initialized = reactive.Value(False)  # Track if chat has been initialized
    selected_year = reactive.Value(datetime.now().year)  # Track selected year for LLM tools
    ink_picker_date = reactive.Value(None)  # Track which date's ink picker is open
    initial_year_set = reactive.Value(False)  # Track if year has been initialized (skip first clear)

    # Load inks from cache on startup
    @reactive.Effect
    def load_cached_inks():
        cache = load_inks_from_cache()
        if cache:
            inks = cache.get("inks", [])
            ink_data.set(inks)
            ui.notification_show(f"Loaded {len(inks)} inks from cache", type="message", duration=3)

    # Load default session on startup if it exists
    @reactive.Effect
    def load_default_session():
        import json
        default_session_path = "session_default.json"
        if os.path.exists(default_session_path):
            try:
                with open(default_session_path, "r") as f:
                    loaded = json.load(f)
                # Support both old format (flat dict) and new format (with assignments/themes)
                if "assignments" in loaded:
                    # New format
                    session_assignments.set(loaded.get("assignments", {}))
                    session_themes.set(loaded.get("themes", {}))
                    num_assignments = len(loaded.get("assignments", {}))
                    num_themes = len(loaded.get("themes", {}))
                    ui.notification_show(f"Loaded default session ({num_assignments} assignments, {num_themes} themes)", type="message", duration=3)
                else:
                    # Old format - flat dict of assignments
                    session_assignments.set(loaded)
                    session_themes.set({})
                    ui.notification_show(f"Loaded default session ({len(loaded)} assignments)", type="message", duration=3)
            except Exception as e:
                ui.notification_show(f"Error loading default session: {str(e)}", type="warning")

    # Update API assignments when ink_data changes (these are protected/read-only)
    @reactive.Effect
    @reactive.event(ink_data)
    def sync_api_assignments_from_ink_data():
        inks = ink_data.get()
        year = input.year()
        if not inks:
            api_assignments.set({})
            return

        # Get explicit assignments from API cache - these are protected
        explicit = create_explicit_assignments_only(inks, year)

        api_assignments.set(explicit)

    # Update API assignments when year changes
    @reactive.Effect
    @reactive.event(input.year)
    def sync_api_assignments_from_year():
        inks = ink_data.get()
        if not inks:
            api_assignments.set({})
            return

        year = input.year()

        # Get explicit assignments from API cache
        explicit = create_explicit_assignments_only(inks, year)

        # Update API assignments
        api_assignments.set(explicit)

        # Clear session assignments and themes only on subsequent year changes (not initial load)
        if initial_year_set.get():
            session_assignments.set({})
            session_themes.set({})
        else:
            initial_year_set.set(True)

    # Helper to get merged assignments (API takes precedence over session)
    def get_merged_assignments_dict():
        """Merge session and API assignments. API assignments take precedence."""
        api = api_assignments.get()
        session = session_assignments.get()
        # Session first, then API overwrites (API takes precedence)
        merged = {**session, **api}
        return merged
    
    # Cache status display
    @output
    @render.text
    def cache_status():
        info = get_cache_info()
        return info if info else "No cache"

    # Session status display
    @output
    @render.text
    def session_status():
        session = session_assignments.get()
        api = api_assignments.get()
        themes = session_themes.get()
        if not session and not api and not themes:
            return "No assignments"
        parts = []
        if api:
            parts.append(f"{len(api)} API")
        if session:
            parts.append(f"{len(session)} session")
        if themes:
            parts.append(f"{len(themes)} themes")
        return " + ".join(parts) if parts else "No assignments"

    # Save session as downloadable file
    @render.download(filename=lambda: f"session_{input.year()}.json")
    def save_session():
        import json
        assignments = session_assignments.get()
        themes = session_themes.get()
        if not assignments and not themes:
            ui.notification_show("No session data to save", type="warning")
            return
        # Save in new format with both assignments and themes
        session_data = {
            "assignments": assignments,
            "themes": themes
        }
        yield json.dumps(session_data, indent=2)

    # Load session from uploaded file
    @reactive.Effect
    @reactive.event(input.load_session)
    def handle_load_session():
        import json
        file_info = input.load_session()
        if not file_info:
            return

        try:
            file_path = file_info[0]["datapath"]
            with open(file_path, "r") as f:
                loaded = json.load(f)
            # Support both old format (flat dict) and new format (with assignments/themes)
            if "assignments" in loaded:
                # New format
                session_assignments.set(loaded.get("assignments", {}))
                session_themes.set(loaded.get("themes", {}))
                num_assignments = len(loaded.get("assignments", {}))
                num_themes = len(loaded.get("themes", {}))
                ui.notification_show(f"Loaded {num_assignments} assignments, {num_themes} themes", type="message")
            else:
                # Old format - flat dict of assignments
                session_assignments.set(loaded)
                session_themes.set({})
                ui.notification_show(f"Loaded {len(loaded)} assignments", type="message")
        except Exception as e:
            ui.notification_show(f"Error loading file: {str(e)}", type="error")

    # Clear API token
    @reactive.Effect
    @reactive.event(input.clear_token)
    def clear_token():
        ui.update_text("api_token", value="")
        ui.notification_show("API token cleared", type="message")

    # Month label for header
    @output
    @render.ui
    def month_label():
        year = input.year()
        month = current_month.get()
        month_name = datetime(year, month, 1).strftime("%B")
        return ui.span(month_name, class_="month-label")

    # Theme label for header
    @output
    @render.ui
    def theme_label():
        year = input.year()
        month = current_month.get()
        month_key = f"{year}-{month:02d}"

        # Check session themes first
        themes = session_themes.get()
        if month_key in themes:
            theme_data = themes[month_key]
            theme_name = theme_data.get("theme", "")
            theme_desc = theme_data.get("description", "")
            if theme_name:
                return ui.span(
                    ui.strong(theme_name, class_="theme-name"),
                    ui.span(" — ", class_="theme-separator") if theme_desc else "",
                    ui.span(theme_desc, class_="theme-description") if theme_desc else "",
                    class_="theme-container"
                )

        # Fall back to checking API ink comments
        inks = ink_data.get()
        if not inks:
            return ui.span()

        daily = get_daily_assignments()
        first_day_str = f"{year}-{month:02d}-01"
        first_day_ink_idx = daily.get(first_day_str)

        if first_day_ink_idx is None or first_day_ink_idx >= len(inks):
            return ui.span()

        first_day_ink = inks[first_day_ink_idx]
        private_comment = first_day_ink.get("private_comment", "")
        theme_info = parse_theme_from_comment(private_comment, year)

        if not theme_info:
            return ui.span()

        return ui.span(
            ui.strong(theme_info["theme"], class_="theme-name"),
            ui.span(" — ", class_="theme-separator"),
            ui.span(theme_info["theme_description"], class_="theme-description"),
            class_="theme-container"
        )

    # Navigate to previous month
    @reactive.Effect
    @reactive.event(input.prev_month)
    def prev_month():
        current_year = input.year()
        month = current_month.get()

        if month == 1:
            # Go to December of previous year
            ui.update_numeric("year", value=current_year - 1)
            current_month.set(12)
        else:
            # Go to previous month
            current_month.set(month - 1)

    # Navigate to next month
    @reactive.Effect
    @reactive.event(input.next_month)
    def next_month():
        current_year = input.year()
        month = current_month.get()

        if month == 12:
            # Go to January of next year
            ui.update_numeric("year", value=current_year + 1)
            current_month.set(1)
        else:
            # Go to next month
            current_month.set(month + 1)

    # Fetch inks from API with pagination
    @reactive.Effect
    @reactive.event(input.fetch_inks)
    def fetch_inks():
        try:
            token = input.api_token()
        except Exception:
            # Try to get from environment variable if input not available
            token = DEFAULT_API_TOKEN

        if not token:
            ui.notification_show("Please enter an API token in Settings", type="error")
            return

        try:
            # Show loading notification
            ui.notification_show("Fetching inks from API...", duration=None, id="fetch_loading", type="message")

            # Fetch all pages of inks
            inks = fetch_all_collected_inks(token)

            # Save to cache FIRST (before setting reactive value)
            save_inks_to_cache(inks)

            # Then update reactive value
            ink_data.set(inks)

            # Remove loading notification and show success
            ui.notification_remove("fetch_loading")
            ui.notification_show(
                f"Successfully fetched {len(inks)} inks and saved to cache!",
                type="message"
            )
        except Exception as e:
            ui.notification_remove("fetch_loading")
            ui.notification_show(f"Error fetching inks: {str(e)}", type="error")

    # Get daily assignments for the selected month (merged view)
    @reactive.Calc
    def get_daily_assignments():
        # Update selected_year when year input changes
        selected_year.set(input.year())
        merged = get_merged_assignments_dict()
        return merged

    # Track button clicks for remove buttons
    _remove_button_clicks = {}

    @reactive.Effect
    def observe_remove_buttons():
        """Handle remove button clicks in list view."""
        year = input.year()
        month = current_month.get()
        num_days = monthrange(year, month)[1]

        for day in range(1, num_days + 1):
            date_str = f"{year}-{month:02d}-{day:02d}"
            button_id = f"remove_{date_str.replace('-', '_')}"

            try:
                current_clicks = getattr(input, button_id, lambda: 0)()
                prev_clicks = _remove_button_clicks.get(button_id, 0)

                if current_clicks > prev_clicks:
                    _remove_button_clicks[button_id] = current_clicks
                    new_session, result = move_ink_assignment(
                        session=session_assignments.get(),
                        api=api_assignments.get(),
                        from_date=date_str,
                        to_date=None,
                        inks=ink_data.get()
                    )
                    if result.success:
                        session_assignments.set(new_session)
                    else:
                        ui.notification_show(result.message, type="warning", duration=4)
            except:
                pass

    # Track previous date values for ink collection date pickers
    _ink_collection_prev_dates = {}

    # Track button clicks for assign buttons
    _assign_button_clicks = {}

    # Dynamic observer for assign buttons (ink bottle icons)
    @reactive.Effect
    def observe_assign_buttons():
        """Watch assign buttons and show ink picker modal when clicked."""
        year = input.year()
        month = current_month.get()
        num_days = monthrange(year, month)[1]

        with reactive.isolate():
            daily = get_daily_assignments()

        for day in range(1, num_days + 1):
            date_str = f"{year}-{month:02d}-{day:02d}"
            button_id = f"assign_{date_str.replace('-', '_')}"

            # Skip assigned days
            if date_str in daily:
                continue

            try:
                current_clicks = getattr(input, button_id, lambda: 0)()
                prev_clicks = _assign_button_clicks.get(button_id, 0)

                if current_clicks > prev_clicks:
                    _assign_button_clicks[button_id] = current_clicks
                    # Show ink picker modal for this date
                    ink_picker_date.set(date_str)
                    show_ink_picker_modal(date_str)
            except Exception:
                pass

    # Track modal state - "ready" becomes True after seeing empty placeholder
    _modal_state = {"ready": False}

    def show_ink_picker_modal(date_str):
        """Show the ink picker modal for a specific date."""
        # Mark not ready until we see empty placeholder (avoids stale values)
        _modal_state["ready"] = False

        inks = ink_data.get()
        daily = get_daily_assignments()
        assigned_indices = set(daily.values())

        # Build choices for unassigned inks only
        unassigned_inks = {"": "Select an ink..."} | {
            str(i): f"{ink.get('brand_name', 'Unknown')} - {ink.get('name', 'Unknown')}"
            for i, ink in enumerate(inks)
            if i not in assigned_indices
        }

        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        date_display = date_obj.strftime("%B %d, %Y")

        m = ui.modal(
            ui.p(f"Assign ink to {date_display}:"),
            ui.input_selectize(
                "modal_ink_select",
                None,
                choices=unassigned_inks,
                selected="",
                width="100%"
            ),
            title="Assign Ink",
            easy_close=True,
            footer=None,
            size="s"
        )
        ui.modal_show(m)

    # Handler for modal ink selection - auto-assign on selection
    @reactive.Effect
    def handle_modal_ink_selection():
        """Auto-assign ink when selection is made in modal."""
        date_str = ink_picker_date.get()
        if not date_str:
            return

        try:
            current_val = input.modal_ink_select()
        except Exception:
            return

        # Wait until we see the empty placeholder value before accepting selections
        # This ensures we don't process stale values from a previous modal
        if not current_val:
            _modal_state["ready"] = True
            return

        # Only process if modal is ready (has seen empty value first)
        if not _modal_state["ready"]:
            return

        try:
            ink_idx = int(current_val)
        except ValueError:
            return

        # Mark not ready to prevent double-processing
        _modal_state["ready"] = False

        # Use unified move function (assign = from_date=None)
        session = session_assignments.get()
        api = api_assignments.get()
        inks = ink_data.get()

        new_session, result = move_ink_assignment(
            session=session,
            api=api,
            from_date=None,
            to_date=date_str,
            ink_idx=ink_idx,
            inks=inks
        )

        if not result.success:
            ui.notification_show(result.message, type="warning", duration=3)
            return

        session_assignments.set(new_session)
        ink_name = result.data.get("ink_name", "ink")
        ui.notification_show(f"Assigned {ink_name}", type="message", duration=2)

        # Close the modal and reset state
        ui.modal_remove()
        ink_picker_date.set(None)

    # Track previous date values for inline date pickers (use dict, not reactive)
    _prev_date_values = {}

    # Dynamic observer for inline date pickers (to change assignment dates)
    @reactive.Effect
    def observe_date_pickers():
        """Set up observers for inline date pickers."""
        year = input.year()
        month = current_month.get()
        num_days = monthrange(year, month)[1]

        # Use isolate to read without creating dependency (prevents infinite loop)
        with reactive.isolate():
            session = session_assignments.get()
            api = api_assignments.get()

        # PHASE 1: Read ALL date inputs to establish reactive dependencies
        input_values = {}
        for day in range(1, num_days + 1):
            date_str = f"{year}-{month:02d}-{day:02d}"
            date_input_id = f"date_{date_str.replace('-', '_')}"
            try:
                # Read the input to create reactive dependency
                val = getattr(input, date_input_id, lambda: None)()
                if val:
                    input_values[date_str] = val
            except Exception:
                pass

        # PHASE 2: Process changes for session assignments only
        inks = ink_data.get()
        for date_str, new_date_value in input_values.items():
            # Only process session assignments (not API protected)
            if date_str not in session or date_str in api:
                continue

            date_input_id = f"date_{date_str.replace('-', '_')}"

            try:
                new_date_str = new_date_value.strftime("%Y-%m-%d")
                prev_value = _prev_date_values.get(date_str)

                # Check if date actually changed (not just initial render)
                if prev_value is not None and new_date_str != date_str:
                    # Use unified move function - it derives ink_idx from session
                    new_session, result = move_ink_assignment(
                        session=session,
                        api=api,
                        from_date=date_str,
                        to_date=new_date_str,
                        inks=inks
                    )

                    if not result.success:
                        # Show error and reset date picker
                        ui.notification_show(result.message, type="warning", duration=3)
                        ui.update_date(date_input_id, value=date_str)
                        continue

                    # Update reactive state
                    session_assignments.set(new_session)

                    # Update tracking for displaced ink if any
                    if result.data.get("displaced_ink_idx") is not None:
                        _prev_date_values[new_date_str] = None

                    # Update tracking for moved ink
                    del _prev_date_values[date_str]
                    _prev_date_values[new_date_str] = new_date_str

                    ink_name = result.data.get("ink_name", "ink")
                    ui.notification_show(f"Moved {ink_name} to {new_date_str}", type="message", duration=3)
                    return  # Exit after one change to avoid cascade

                # Update tracked value
                _prev_date_values[date_str] = new_date_str

            except Exception:
                pass

    # Dynamic observer for ink collection date changes and remove buttons
    @reactive.Effect
    def observe_ink_collection_changes():
        """Handle date picker changes and remove buttons in ink collection."""
        inks = ink_data.get()
        if not inks:
            return

        # Use isolate to read without creating dependency (prevents infinite loop)
        with reactive.isolate():
            daily = get_daily_assignments()
            api = api_assignments.get()
            session = session_assignments.get()
        ink_to_date = {idx: date_str for date_str, idx in daily.items()}

        # PHASE 1: Read ALL inputs to establish reactive dependencies
        input_values = {}
        remove_clicks = {}
        for idx in range(len(inks)):
            try:
                current_date = ink_to_date.get(idx)
                if current_date and current_date in api:
                    continue
                date_input_id = f"ink_date_{idx}"
                remove_btn_id = f"ink_remove_{idx}"
                input_values[idx] = getattr(input, date_input_id, lambda: None)()
                remove_clicks[idx] = getattr(input, remove_btn_id, lambda: 0)()
            except Exception:
                pass

        # PHASE 2: Process changes (only handle first change found)
        change_processed = False
        for idx in range(len(inks)):
            current_date = ink_to_date.get(idx)
            if current_date and current_date in api:
                continue

            try:
                # Handle remove button (only for session assignments)
                if not change_processed and current_date and remove_clicks.get(idx, 0) > 0:
                    # Unassign - function derives ink_idx from session
                    new_session, result = move_ink_assignment(
                        session=session,
                        api=api,
                        from_date=current_date,
                        to_date=None,
                        inks=inks
                    )

                    if result.success:
                        session_assignments.set(new_session)
                        ink_name = result.data.get("ink_name", "ink")
                        ui.notification_show(f"Removed {ink_name}", type="message", duration=3)
                        change_processed = True
                    continue

                # Handle date picker changes
                new_date_value = input_values.get(idx)
                if not new_date_value:
                    _ink_collection_prev_dates[idx] = None
                    continue

                new_date_str = new_date_value.strftime("%Y-%m-%d")
                prev_value = _ink_collection_prev_dates.get(idx)

                # Check if this is a real change (not initial render)
                is_new_assignment = not current_date and prev_value is None
                is_date_change = prev_value is not None and new_date_str != prev_value

                if not change_processed and (is_new_assignment or is_date_change):
                    # Use unified move function (handles assign, move, and validation)
                    # Pass ink_idx for new assignments (current_date=None), otherwise derived
                    new_session, result = move_ink_assignment(
                        session=session,
                        api=api,
                        from_date=current_date,  # None for new assignment
                        to_date=new_date_str,
                        ink_idx=idx if current_date is None else None,
                        inks=inks
                    )

                    if not result.success:
                        ui.notification_show(result.message, type="warning", duration=3)
                        ui.update_date(f"ink_date_{idx}", value="")
                        continue

                    # Update tracking for displaced ink if any
                    if result.data.get("displaced_ink_idx") is not None:
                        _ink_collection_prev_dates[result.data["displaced_ink_idx"]] = None

                    session_assignments.set(new_session)
                    ink_name = result.data.get("ink_name", "ink")
                    action = "Moved" if current_date else "Assigned"
                    ui.notification_show(f"{action} {ink_name} to {new_date_str}", type="message", duration=3)
                    _ink_collection_prev_dates[idx] = new_date_str
                    change_processed = True
                    continue

                _ink_collection_prev_dates[idx] = new_date_str

            except Exception:
                pass

    # Main view output
    @output
    @render.ui
    def main_view():
        is_list_view = input.view_mode()
        
        if is_list_view:
            return list_view()
        else:
            return calendar_view()
    
    # Calendar view
    def calendar_view():
        inks = ink_data.get()
        if not inks:
            return ui.p("No inks loaded. Please fetch your collection first.")

        daily = get_daily_assignments()
        year = input.year()
        month = current_month.get()  # Use reactive value instead of input

        num_days = monthrange(year, month)[1]
        first_weekday = datetime(year, month, 1).weekday()

        # Build calendar grid
        weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        # Header row
        header = ui.div(
            *[ui.div(day, class_="calendar-weekday")
              for day in weekdays],
            class_="calendar-header"
        )
        
        # Calendar days - use actual empty divs for grid cells before first day
        cells = [ui.div(class_="calendar-cell-empty") for _ in range(first_weekday)]
        
        for day in range(1, num_days + 1):
            date_str = f"{year}-{month:02d}-{day:02d}"
            ink_idx = daily.get(date_str)
            
            if ink_idx is not None and ink_idx < len(inks):
                ink = inks[ink_idx]
                ink_name = ink.get("name", "Unknown")
                brand = ink.get("brand_name", "")
                ink_color = ink.get("color", "#cccccc")

                # Can delete if it's a session assignment (not from API)
                api = api_assignments.get()
                session = session_assignments.get()
                can_delete = date_str in session and date_str not in api

                # Build cell content with optional remove button
                cell_components = [
                    ui.div(
                        ui.strong(str(day), class_="calendar-day-number"),
                        ui.div(ink_swatch_svg(ink_color, "lg")),
                        class_="calendar-cell-header"
                    ),
                    ui.span(brand, class_="calendar-brand"),
                    ui.span(ink_name, class_="calendar-ink-name")
                ]

                # Build the main content div
                main_content = ui.div(
                    *cell_components,
                    class_="calendar-cell-content"
                )

                # Build the cell with optional remove button overlay
                if can_delete:
                    remove_btn = ui.input_action_button(
                        f"remove_{date_str.replace('-', '_')}",
                        "✕",
                        class_="btn-sm calendar-remove-btn"
                    )
                    cell_content = ui.div(
                        remove_btn,
                        main_content,
                        class_="calendar-cell-assigned"
                    )
                else:
                    cell_content = ui.div(
                        main_content,
                        class_="calendar-cell-assigned"
                    )
            else:
                cell_content = ui.div(
                    ui.strong(str(day)),
                    class_="calendar-cell"
                )
            
            cells.append(cell_content)
        
        # Fill remaining cells with empty divs
        while len(cells) % 7 != 0:
            cells.append(ui.div(class_="calendar-cell-empty"))
        
        calendar_grid = ui.div(
            *cells,
            class_="calendar-grid"
        )

        return ui.div(header, calendar_grid)
    
    # List view
    def list_view():
        inks = ink_data.get()
        if not inks:
            return ui.p("No inks loaded. Please fetch your collection first.")

        daily = get_daily_assignments()
        year = input.year()
        month = current_month.get()  # Use reactive value instead of input
        api = api_assignments.get()
        session = session_assignments.get()

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
            ink_idx = daily.get(date_str)

            # Date column
            date_col = ui.div(
                ui.strong(date_obj.strftime("%a, %b %d")),
                class_="list-date-col"
            )

            if ink_idx is not None and ink_idx < len(inks):
                ink = inks[ink_idx]
                color = ink.get("color", "#888888")
                brand = ink.get("brand_name", "Unknown")
                name = ink.get("name", "Unknown")

                # Can edit if it's a session assignment (not from API)
                can_edit = date_str in session and date_str not in api
                is_api = date_str in api

                # Ink swatch (small)
                swatch = ink_swatch_svg(color, "sm")

                # Brand and name columns
                brand_col = ui.div(brand, class_="list-brand-col")
                name_col = ui.div(name, class_="list-name-col")

                # Actions column
                if can_edit:
                    action_components = [
                        ui.div(ui.input_date(f"date_{date_str.replace('-', '_')}", "", value=date_obj.date()), class_="calendar-icon-picker"),
                        ui.input_action_button(
                            f"remove_{date_str.replace('-', '_')}",
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

                row = ui.div(
                    date_col,
                    ui.div(swatch, class_="list-swatch-col"),
                    brand_col,
                    name_col,
                    action_col,
                    class_="list-row"
                )
            else:
                # Unassigned day - with ink bottle icon to assign
                ink_bottle_svg = ui.HTML('''<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#666" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M10 2h4v2h-4z"/>
                    <path d="M8 4h8l1 4H7l1-4z"/>
                    <path d="M7 8h10v12a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2V8z"/>
                    <path d="M9 13h6v5H9z" fill="#666" opacity="0.3"/>
                </svg>''')

                assign_button = ui.input_action_button(
                    f"assign_{date_str.replace('-', '_')}",
                    ink_bottle_svg,
                    class_="ink-assign-btn",
                    title="Assign ink to this date"
                )

                row = ui.div(
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

            rows.append(row)

        list_content = ui.div(*rows, class_="list-content")

        return ui.div(header_row, list_content)

    # Ink collection view with search and inline assignment
    @output
    @render.ui
    def ink_collection_view():
        inks = ink_data.get()
        if not inks:
            return ui.p("No inks loaded. Please fetch your collection first.")

        daily = get_daily_assignments()
        api = api_assignments.get()
        # Explicit dependency to ensure re-render on session changes
        _ = session_assignments.get()

        # Build reverse lookup: ink_idx -> date_str
        ink_to_date = {idx: date_str for date_str, idx in daily.items()}

        # Get search filter
        search_term = input.ink_search().lower().strip() if input.ink_search() else ""

        # Table header
        header_row = ui.div(
            ui.div("Color", class_="list-col-color"),
            ui.div("Brand", class_="list-col-brand"),
            ui.div("Name", class_="list-col-name"),
            ui.div("Assignment", class_="list-col-actions"),
            class_="ink-collection-header"
        )

        rows = []
        for idx, ink in enumerate(inks):
            brand = ink.get("brand_name", "Unknown")
            name = ink.get("name", "Unknown")
            color = ink.get("color", "#888888")

            # Apply search filter
            if search_term and search_term not in brand.lower() and search_term not in name.lower():
                continue

            assigned_date = ink_to_date.get(idx)

            # Ink swatch (small)
            swatch = ink_swatch_svg(color, "sm")

            # Brand and name columns
            brand_col = ui.div(brand, class_="ink-collection-brand-col")
            name_col = ui.div(name, class_="list-name-col")

            # Assignment column
            is_api = assigned_date and assigned_date in api
            is_session = assigned_date and not is_api

            if is_api:
                # API assignment - read only
                date_obj = datetime.strptime(assigned_date, "%Y-%m-%d")
                assign_col = ui.div(
                    ui.span(date_obj.strftime("%b %d, %Y"), class_="api-date-display"),
                    ui.span("swatched", class_="api-badge"),
                    class_="ink-collection-assign-col"
                )
            else:
                # Editable - date picker for both session and unassigned
                date_value = datetime.strptime(assigned_date, "%Y-%m-%d").date() if assigned_date else ""
                components = []
                if is_session:
                    components.append(ui.input_action_button(
                        f"ink_remove_{idx}",
                        "Remove",
                        class_="btn-sm btn-outline-danger ink-collection-remove-btn"
                    ))
                components.append(ui.div(ui.input_date(f"ink_date_{idx}", "", value=date_value), class_="ink-collection-date-picker"))
                assign_col = ui.div(*components, class_="ink-collection-assign-col")

            row = ui.div(
                ui.div(swatch, class_="list-swatch-col"),
                brand_col,
                name_col,
                assign_col,
                class_="list-row"
            )
            rows.append(row)

        count_text = f"Showing {len(rows)} of {len(inks)} inks" if search_term else f"{len(inks)} inks"
        count_display = ui.div(count_text, class_="ink-collection-count")

        list_content = ui.div(*rows, class_="list-content")

        return ui.div(count_display, header_row, list_content)
    
    # Month assignment table
    @output
    @render.data_frame
    def month_assignment():
        inks = ink_data.get()
        current_assignments = get_merged_assignments_dict()
        year = input.year()

        if not inks or not current_assignments:
            return pd.DataFrame()

        # Group assignments by month using tested function
        rows = []
        for month_num in range(1, 13):
            month_name = datetime(2000, month_num, 1).strftime("%B")
            ink_indices = get_month_summary(current_assignments, year, month_num)
            ink_names = [
                f"{inks[idx].get('brand_name', '')} - {inks[idx].get('name', '')}"
                for idx in ink_indices if idx < len(inks)
            ]

            rows.append({
                "Month": month_name,
                "Number of Inks": len(ink_names),
                "Inks": ", ".join(ink_names[:3]) + ("..." if len(ink_names) > 3 else "")
            })

        df = pd.DataFrame(rows)
        return render.DataGrid(df, width="100%")

    def initialize_chat():
        """Initialize the LLM chat with ink collection context."""
        inks = ink_data.get()
        if not inks:
            return None

        try:
            # Get provider from settings (with default fallback)
            try:
                provider = input.llm_provider()
            except:
                provider = "openai"  # Fallback to default if not set
            
            # Create chat instance
            year = selected_year.get()
            system_message = f"""You are an expert fountain pen ink curator helping organize a collection of {len(inks)} inks for the year {year}.

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

            chat_obj = create_llm_chat(provider, system_prompt=system_message)

            # Register tools with session/api assignment state
            tool_functions, snapshot_updater = create_tool_functions(
                ink_data, selected_year, session_assignments, api_assignments, session_themes
            )
            for tool_func in tool_functions:
                chat_obj.register_tool(tool_func)

            return chat_obj, snapshot_updater

        except Exception as e:
            print(f"Chat initialization error: {traceback.format_exc()}")
            return None

    # Handle chat messages
    @chat.on_user_submit
    async def on_user_submit(user_input: str):
        """Handle user messages in the chat."""
        # Initialize chat if needed
        if not chat_initialized.get():
            inks = ink_data.get()
            if not inks:
                await chat.append_message("❌ Please fetch your inks first using the sidebar.")
                return

            result = initialize_chat()
            if not result:
                await chat.append_message("❌ Error initializing chat. Please check your API key in the .env file.")
                return

            chat_obj, snapshot_updater = result
            llm_chat_instance.set((chat_obj, snapshot_updater))
            chat_initialized.set(True)

            # Don't return - continue to process the user's message below

        # Get response from LLM
        stored = llm_chat_instance.get()
        if not stored:
            await chat.append_message("❌ Chat not initialized. Please reset and try again.")
            return

        chat_obj, snapshot_updater = stored

        try:
            # Update snapshot from reactive values before async call
            snapshot_updater()
            # Use stream_async with content="all" to show tool calls in the chat UI
            response = await chat_obj.stream_async(user_input, content="all")
            await chat.append_message_stream(response)

        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            print(f"Chat error: {traceback.format_exc()}")
            await chat.append_message(error_msg)

    # Reset chat
    @reactive.Effect
    @reactive.event(input.reset_chat)
    async def reset_chat_handler():
        """Reset the chat conversation."""
        llm_chat_instance.set(None)
        chat_initialized.set(False)
        await chat.clear_messages()
        ui.notification_show("Chat reset! Send a message to start a new conversation.", type="message")


app = App(app_ui, server)
