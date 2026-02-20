from shiny import App, ui, render, reactive
from datetime import datetime
import pandas as pd
import os
import logging
import json
import traceback

# Configure chatlas logging before importing chatlas-related modules
os.environ["CHATLAS_LOG"] = "debug"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logging.getLogger("api_client").setLevel(logging.DEBUG)

from dotenv import load_dotenv
from assignment_logic import (
    create_explicit_assignments_only,
    get_month_summary,
    move_ink_assignment,
    swap_ink_assignments,
    check_overwrite_conflict,
    build_swatch_comment_json,
    remove_swatch_from_comment,
)
from api_client import fetch_all_collected_inks, update_ink_private_comment, fetch_single_ink
from ink_cache import save_inks_to_cache, load_inks_from_cache, get_cache_info
from app_helpers import (
    parse_session_data,
    get_month_theme,
    prepare_save_data,
    prepare_post_save_updates,
    get_month_dates,
    make_button_id,
    detect_new_click,
)
from views import (
    render_calendar_view,
    render_list_view,
    render_ink_collection_view,
)
from chat_setup import initialize_chat_session

# Load environment variables from .env file
load_dotenv()

# Get API token from environment (if available)
DEFAULT_API_TOKEN = os.getenv("FPC_API_TOKEN", "")

app_ui = ui.page_fluid(
    ui.include_css("styles.css"),
    ui.include_js("calendar_drag.js"),

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
                    ui.output_ui("save_all_month_btn"),
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
        default_session_path = "session_default.json"
        if os.path.exists(default_session_path):
            try:
                with open(default_session_path, "r") as f:
                    loaded = json.load(f)
                assignments, themes = parse_session_data(loaded)
                session_assignments.set(assignments)
                session_themes.set(themes)
                ui.notification_show(
                    f"Loaded default session ({len(assignments)} assignments, {len(themes)} themes)",
                    type="message", duration=3
                )
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
        file_info = input.load_session()
        if not file_info:
            return

        try:
            file_path = file_info[0]["datapath"]
            with open(file_path, "r") as f:
                loaded = json.load(f)
            assignments, themes = parse_session_data(loaded)
            session_assignments.set(assignments)
            session_themes.set(themes)
            ui.notification_show(
                f"Loaded {len(assignments)} assignments, {len(themes)} themes",
                type="message"
            )
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

        # Get theme using extracted business logic
        theme_info = get_month_theme(
            year, month,
            session_themes.get(),
            ink_data.get(),
            get_daily_assignments()
        )

        # Pencil icon SVG for edit button
        edit_icon = ui.HTML('''<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
        </svg>''')

        # No theme - show "+ Theme" button
        if theme_info.source == "none":
            return ui.div(
                ui.input_action_button("edit_theme", "+ Theme", class_="theme-set-btn"),
                class_="theme-container"
            )

        # Theme exists - show it with edit button
        return ui.div(
            ui.span(
                ui.strong(theme_info.theme, class_="theme-name"),
                ui.span(" — ", class_="theme-separator") if theme_info.description else "",
                ui.span(theme_info.description, class_="theme-description") if theme_info.description else "",
                class_="theme-text"
            ),
            ui.input_action_button("edit_theme", edit_icon, class_="theme-edit-btn"),
            class_="theme-container"
        )

    # Save All Month button - only shows when there are unsaved session assignments for this month
    @output
    @render.ui
    def save_all_month_btn():
        year = input.year()
        month = current_month.get()

        session = session_assignments.get()
        api = api_assignments.get()

        # Count unsaved session assignments for this month
        month_prefix = f"{year}-{month:02d}"
        unsaved_count = sum(
            1 for date_str in session
            if date_str.startswith(month_prefix) and date_str not in api
        )

        if unsaved_count == 0:
            return ui.span()  # Return empty span when nothing to save

        # Save icon SVG
        save_icon = ui.HTML('''<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
            <polyline points="17 21 17 13 7 13 7 21"/>
            <polyline points="7 3 7 8 15 8"/>
        </svg>''')

        return ui.input_action_button(
            "save_all_month",
            ui.span(save_icon, f" Save All ({unsaved_count})"),
            class_="btn-primary btn-sm save-all-month-btn"
        )

    # Handle Save All Month button click
    @reactive.Effect
    @reactive.event(input.save_all_month)
    async def handle_save_all_month():
        year = input.year()
        month = current_month.get()

        session = session_assignments.get()
        api = api_assignments.get()
        inks = ink_data.get()
        themes = session_themes.get()

        # Get API token
        try:
            token = input.api_token()
        except Exception:
            token = DEFAULT_API_TOKEN

        if not token:
            ui.notification_show("API token not found. Please set in Settings.", type="error")
            return

        # Find all unsaved session assignments for this month
        month_prefix = f"{year}-{month:02d}"
        to_save = [
            (date_str, session[date_str])
            for date_str in sorted(session.keys())
            if date_str.startswith(month_prefix) and date_str not in api
        ]

        if not to_save:
            ui.notification_show("No unsaved assignments for this month", type="warning")
            return

        ui.notification_show(f"Saving {len(to_save)} assignments...", duration=None, id="bulk_save_loading")

        saved_count = 0
        error_count = 0

        for date_str, ink_idx in to_save:
            try:
                ink = inks[ink_idx]

                # Fetch fresh data from API
                try:
                    fresh_ink = fetch_single_ink(token, ink["id"])
                except Exception:
                    fresh_ink = ink

                # Get save data
                save_data = prepare_save_data(date_str, year, themes)
                new_data = {
                    "date": save_data.date,
                    "theme": save_data.theme,
                    "theme_description": save_data.theme_description
                }

                # Build updated comment JSON
                updated_comment = build_swatch_comment_json(
                    fresh_ink.get("private_comment", ""),
                    year,
                    new_data["date"],
                    new_data.get("theme"),
                    new_data.get("theme_description")
                )

                # Call API
                update_ink_private_comment(token, fresh_ink["id"], updated_comment)

                # Prepare state updates
                updates = prepare_post_save_updates(
                    ink_data.get(),
                    ink_idx,
                    updated_comment,
                    date_str,
                    year,
                    session_assignments.get()
                )

                # Apply state updates
                ink_data.set(updates.updated_inks)
                save_inks_to_cache(updates.updated_inks)
                api_assignments.set(updates.new_api_assignments)
                session_assignments.set(updates.new_session_assignments)

                saved_count += 1

            except Exception as e:
                error_count += 1
                ink_name = f"{inks[ink_idx].get('brand_name', '')} {inks[ink_idx].get('name', '')}"
                ui.notification_show(f"Error saving {ink_name}: {str(e)}", type="error", duration=5)

        ui.notification_remove("bulk_save_loading")

        if error_count == 0:
            ui.notification_show(f"Successfully saved all {saved_count} assignments!", type="message", duration=3)
        else:
            ui.notification_show(f"Saved {saved_count} of {len(to_save)} assignments ({error_count} errors)", type="warning", duration=5)

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

        for date_str in get_month_dates(year, month):
            button_id = make_button_id("remove", date_str)

            try:
                current_clicks = getattr(input, button_id, lambda: 0)()
                prev_clicks = _remove_button_clicks.get(button_id, 0)

                if detect_new_click(current_clicks, prev_clicks):
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

    # Track button clicks for save buttons
    _save_button_clicks = {}

    # Reactive value for pending save (when confirmation is needed)
    pending_save = reactive.Value(None)

    # Reactive value for pending API delete (when confirmation is needed)
    pending_api_delete = reactive.Value(None)

    @reactive.Effect
    def observe_save_buttons():
        """Handle save button clicks in calendar and list views."""
        year = input.year()
        month = current_month.get()

        with reactive.isolate():
            session = session_assignments.get()
            api = api_assignments.get()
            inks = ink_data.get()
            themes = session_themes.get()

        for date_str in get_month_dates(year, month):
            # Only process session assignments (not API)
            if date_str not in session or date_str in api:
                continue

            button_id = make_button_id("save", date_str)
            try:
                current_clicks = getattr(input, button_id, lambda: 0)()
                prev_clicks = _save_button_clicks.get(button_id, 0)

                if detect_new_click(current_clicks, prev_clicks):
                    _save_button_clicks[button_id] = current_clicks
                    ink_idx = session[date_str]
                    handle_save_assignment(date_str, ink_idx, inks, year, themes)
            except:
                pass

    # Track button clicks for ink collection save buttons
    _ink_save_button_clicks = {}

    @reactive.Effect
    def observe_ink_save_buttons():
        """Handle save button clicks in ink collection view."""
        year = input.year()

        with reactive.isolate():
            session = session_assignments.get()
            api = api_assignments.get()
            inks = ink_data.get()
            themes = session_themes.get()

        # Build reverse lookup: ink_idx -> date_str
        session_ink_to_date = {idx: date_str for date_str, idx in session.items() if date_str not in api}

        for idx in range(len(inks)):
            button_id = f"ink_save_{idx}"

            # Only process if this ink has a session assignment
            if idx not in session_ink_to_date:
                continue

            try:
                current_clicks = getattr(input, button_id, lambda: 0)()
                prev_clicks = _ink_save_button_clicks.get(button_id, 0)

                if current_clicks > prev_clicks:
                    _ink_save_button_clicks[button_id] = current_clicks
                    date_str = session_ink_to_date[idx]
                    handle_save_assignment(date_str, idx, inks, year, themes)
            except:
                pass

    def handle_save_assignment(date_str: str, ink_idx: int, inks, year: int, themes):
        """Handle saving a session assignment to API."""
        try:
            ink = inks[ink_idx]
            ink_name = f"{ink.get('brand_name', '')} {ink.get('name', '')}"

            # Get API token
            try:
                token = input.api_token()
            except:
                token = DEFAULT_API_TOKEN

            if not token:
                ui.notification_show("API token not found. Please set in Settings.", type="error")
                return

            # Fetch fresh data from API to check for conflicts
            try:
                fresh_ink = fetch_single_ink(token, ink["id"])
                # Use fresh data for conflict check
                ink_for_conflict_check = fresh_ink
            except Exception as e:
                # If fetch fails, fall back to cached data but warn user
                ui.notification_show(f"Could not verify with API, using cached data: {str(e)}", type="warning", duration=3)
                ink_for_conflict_check = ink

            # Get theme for this month if exists
            save_data = prepare_save_data(date_str, year, themes)
            new_data = {
                "date": save_data.date,
                "theme": save_data.theme,
                "theme_description": save_data.theme_description
            }

            # Check for conflicts using fresh API data
            conflict = check_overwrite_conflict(ink_for_conflict_check, year)

            if conflict:
                # Show confirmation modal (pass fresh ink data for the save)
                show_save_confirmation_modal(date_str, ink_idx, ink_name, conflict, new_data, ink_for_conflict_check, year)
            else:
                # No conflict, save immediately (use fresh ink data)
                perform_save(date_str, ink_idx, ink_for_conflict_check, year, new_data)

        except Exception as e:
            ui.notification_show(f"Error preparing save: {str(e)}", type="error", duration=5)

    def show_save_confirmation_modal(date_str: str, ink_idx: int, ink_name: str, conflict, new_data, ink, year: int):
        """Show confirmation dialog when overwriting existing data."""
        # Build comparison table
        existing_date = conflict.get("existing_date", "(none)")
        existing_theme = conflict.get("existing_theme") or "(none)"
        new_theme = new_data.get("theme") or "(none)"

        comparison = ui.div(
            ui.div(
                ui.strong("Warning: This will overwrite existing swatch data for this year"),
                class_="save-conflict-warning"
            ),
            ui.tags.table(
                ui.tags.thead(
                    ui.tags.tr(
                        ui.tags.th("Field"),
                        ui.tags.th("Current"),
                        ui.tags.th("New")
                    )
                ),
                ui.tags.tbody(
                    ui.tags.tr(
                        ui.tags.td("Date"),
                        ui.tags.td(existing_date, class_="save-diff-old"),
                        ui.tags.td(new_data["date"], class_="save-diff-new")
                    ),
                    ui.tags.tr(
                        ui.tags.td("Theme"),
                        ui.tags.td(existing_theme, class_="save-diff-old"),
                        ui.tags.td(new_theme, class_="save-diff-new")
                    )
                ),
                class_="save-diff-table"
            )
        )

        m = ui.modal(
            ui.p(f"Save assignment for {ink_name}?"),
            comparison,
            title="Confirm Overwrite",
            easy_close=True,
            footer=ui.div(
                ui.input_action_button("confirm_save", "Save", class_="btn-primary"),
                ui.input_action_button("cancel_save", "Cancel", class_="btn-secondary"),
                class_="modal-footer-buttons"
            )
        )
        ui.modal_show(m)

        # Store pending save info
        pending_save.set({
            "date_str": date_str,
            "ink_idx": ink_idx,
            "ink": ink,
            "year": year,
            "new_data": new_data
        })

    @reactive.Effect
    @reactive.event(input.confirm_save)
    def handle_confirm_save():
        """Execute save after confirmation."""
        save_info = pending_save.get()
        if not save_info:
            return

        perform_save(
            save_info["date_str"],
            save_info["ink_idx"],
            save_info["ink"],
            save_info["year"],
            save_info["new_data"]
        )
        ui.modal_remove()
        pending_save.set(None)

    @reactive.Effect
    @reactive.event(input.cancel_save)
    def handle_cancel_save():
        """Cancel save operation."""
        ui.modal_remove()
        pending_save.set(None)

    # Track button clicks for API delete buttons (list view)
    _api_delete_button_clicks = {}

    @reactive.Effect
    def observe_api_delete_buttons():
        """Handle API delete button clicks in list view."""
        year = input.year()
        month = current_month.get()

        inks = ink_data.get()
        if not inks:
            return

        with reactive.isolate():
            api = api_assignments.get()

        for date_str in get_month_dates(year, month):
            # Only process API assignments
            if date_str not in api:
                continue

            button_id = make_button_id("api_delete", date_str)

            try:
                current_clicks = getattr(input, button_id, lambda: 0)()
                prev_clicks = _api_delete_button_clicks.get(button_id, 0)

                if current_clicks > prev_clicks:
                    _api_delete_button_clicks[button_id] = current_clicks
                    ink_idx = api[date_str]
                    ink = inks[ink_idx]
                    show_api_delete_confirmation_modal(date_str, ink_idx, ink)
            except:
                pass

    def show_api_delete_confirmation_modal(date_str: str, ink_idx: int, ink: dict):
        """Show confirmation dialog before deleting an API assignment."""
        ink_name = f"{ink.get('brand_name', '')} {ink.get('name', '')}"
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        date_display = date_obj.strftime("%B %d, %Y")
        year = date_obj.year

        warning_content = ui.div(
            ui.div(
                ui.strong("Warning: This will change data on FPC!"),
                class_="api-delete-warning"
            ),
            ui.p("You are about to remove the swatch assignment for:"),
            ui.div(
                ui.tags.table(
                    ui.tags.tbody(
                        ui.tags.tr(
                            ui.tags.td("Ink:", class_="api-delete-label"),
                            ui.tags.td(ink_name, class_="api-delete-value")
                        ),
                        ui.tags.tr(
                            ui.tags.td("Date:", class_="api-delete-label"),
                            ui.tags.td(date_display, class_="api-delete-value")
                        ),
                        ui.tags.tr(
                            ui.tags.td("Year:", class_="api-delete-label"),
                            ui.tags.td(str(year), class_="api-delete-value")
                        )
                    ),
                    class_="api-delete-table"
                ),
                class_="api-delete-details"
            ),
            ui.p(
                "This will remove the swatch date from the ink's data in the API. ",
                class_="api-delete-explanation"
            )
        )

        m = ui.modal(
            warning_content,
            title="Delete API Assignment?",
            easy_close=True,
            footer=ui.div(
                ui.input_action_button("cancel_api_delete", "Cancel", class_="btn-secondary"),
                ui.input_action_button("confirm_api_delete", "Remove", class_="btn-danger"),
                class_="modal-footer-buttons"
            )
        )
        ui.modal_show(m)

        # Store pending delete info
        pending_api_delete.set({
            "date_str": date_str,
            "ink_idx": ink_idx,
            "ink": ink,
            "year": year
        })

    @reactive.Effect
    @reactive.event(input.confirm_api_delete)
    def handle_confirm_api_delete():
        """Execute API delete after confirmation."""
        delete_info = pending_api_delete.get()
        if not delete_info:
            return

        perform_api_delete(
            delete_info["date_str"],
            delete_info["ink_idx"],
            delete_info["ink"],
            delete_info["year"]
        )
        ui.modal_remove()
        pending_api_delete.set(None)

    @reactive.Effect
    @reactive.event(input.cancel_api_delete)
    def handle_cancel_api_delete():
        """Cancel API delete operation."""
        ui.modal_remove()
        pending_api_delete.set(None)

    def perform_api_delete(date_str: str, ink_idx: int, ink: dict, year: int):
        """Execute the actual API delete operation."""
        try:
            ink_name = f"{ink.get('brand_name', '')} {ink.get('name', '')}"

            # Get API token
            try:
                token = input.api_token()
            except:
                token = DEFAULT_API_TOKEN

            if not token:
                ui.notification_show("API token not found. Please set in Settings.", type="error")
                return

            # Show loading notification
            ui.notification_show("Deleting from API...", duration=None, id="delete_loading", type="message")

            # Fetch fresh data from API
            try:
                fresh_ink = fetch_single_ink(token, ink["id"])
            except Exception as e:
                ui.notification_remove("delete_loading")
                ui.notification_show(f"Could not fetch ink data: {str(e)}", type="error")
                return

            # Build updated comment JSON with swatch data removed
            updated_comment = remove_swatch_from_comment(
                fresh_ink.get("private_comment", ""),
                year
            )

            # Call API to update
            update_ink_private_comment(token, fresh_ink["id"], updated_comment)

            # Update local ink data
            inks = ink_data.get().copy()
            inks[ink_idx] = {**inks[ink_idx], "private_comment": updated_comment}
            ink_data.set(inks)
            save_inks_to_cache(inks)

            # Rebuild API assignments from updated ink data
            new_api = create_explicit_assignments_only(inks, year)
            api_assignments.set(new_api)

            # Show success
            ui.notification_remove("delete_loading")
            ui.notification_show(f"Deleted assignment for {ink_name}", type="message", duration=3)

        except Exception as e:
            ui.notification_remove("delete_loading")
            error_msg = str(e)
            if hasattr(e, 'response'):
                error_msg = f"{e.response.status_code}: {e.response.text[:100]}"
            ui.notification_show(f"Error deleting: {error_msg}", type="error", duration=7)

    def perform_save(date_str: str, ink_idx: int, ink, year: int, new_data):
        """Execute the actual API save operation."""
        try:
            # Show loading notification
            ui.notification_show("Saving to API...", duration=None, id="save_loading", type="message")

            # Build updated comment JSON
            updated_comment = build_swatch_comment_json(
                ink.get("private_comment", ""),
                year,
                new_data["date"],
                new_data.get("theme"),
                new_data.get("theme_description")
            )

            # Get API token
            try:
                token = input.api_token()
            except:
                token = DEFAULT_API_TOKEN

            if not token:
                ui.notification_remove("save_loading")
                ui.notification_show("API token not found. Please set in Settings.", type="error")
                return

            # Call API
            update_ink_private_comment(token, ink["id"], updated_comment)

            # Prepare all state updates using extracted business logic
            updates = prepare_post_save_updates(
                ink_data.get(),
                ink_idx,
                updated_comment,
                date_str,
                year,
                session_assignments.get()
            )

            # Apply state updates
            ink_data.set(updates.updated_inks)
            save_inks_to_cache(updates.updated_inks)
            api_assignments.set(updates.new_api_assignments)
            session_assignments.set(updates.new_session_assignments)

            # Show success
            ui.notification_remove("save_loading")
            ink_name = f"{ink.get('brand_name', '')} {ink.get('name', '')}"
            ui.notification_show(f"Saved {ink_name} to API!", type="message", duration=3)

        except Exception as e:
            ui.notification_remove("save_loading")
            error_msg = str(e)
            if hasattr(e, 'response'):
                error_msg = f"{e.response.status_code}: {e.response.text[:100]}"
            ui.notification_show(f"Error saving: {error_msg}", type="error", duration=7)

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

        with reactive.isolate():
            daily = get_daily_assignments()

        for date_str in get_month_dates(year, month):
            # Skip assigned days
            if date_str in daily:
                continue

            button_id = make_button_id("assign", date_str)
            try:
                current_clicks = getattr(input, button_id, lambda: 0)()
                prev_clicks = _assign_button_clicks.get(button_id, 0)

                if detect_new_click(current_clicks, prev_clicks):
                    _assign_button_clicks[button_id] = current_clicks
                    # Show ink picker modal for this date
                    ink_picker_date.set(date_str)
                    show_ink_picker_modal(date_str)
            except Exception:
                pass

    # Reactive value for ink picker search
    ink_picker_search = reactive.Value("")

    def show_ink_picker_modal(date_str):
        """Show the ink picker modal for a specific date."""
        # Reset search when opening modal
        ink_picker_search.set("")

        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        date_display = date_obj.strftime("%B %d, %Y")

        m = ui.modal(
            ui.p(f"Assign ink to {date_display}:", class_="ink-picker-subtitle"),
            ui.input_text(
                "ink_picker_search_input",
                None,
                placeholder="Search inks...",
                width="100%"
            ),
            ui.output_ui("ink_picker_list"),
            ui.tags.script("""
                // Focus search input when modal opens
                setTimeout(function() {
                    var searchInput = document.getElementById('ink_picker_search_input');
                    if (searchInput) searchInput.focus();
                }, 100);
            """),
            title="Assign Ink",
            easy_close=True,
            footer=None,
            size="m"
        )
        ui.modal_show(m)

    # Update search reactive value when input changes
    @reactive.Effect
    def sync_ink_picker_search():
        try:
            search_val = input.ink_picker_search_input()
            ink_picker_search.set(search_val or "")
        except Exception:
            pass

    # Render the filtered ink list for the picker modal
    @output
    @render.ui
    def ink_picker_list():
        date_str = ink_picker_date.get()
        if not date_str:
            return ui.div()

        inks = ink_data.get()
        if not inks:
            return ui.p("No inks loaded.")

        session = session_assignments.get()
        api = api_assignments.get()
        search_query = ink_picker_search.get().lower()

        # Build list of inks to show:
        # 1. Unassigned inks
        # 2. Session-assigned inks (with date label)
        # API-assigned inks are excluded (can't reassign them)
        ink_items = []

        # Get all assignments
        daily = get_daily_assignments()
        assigned_indices = set(daily.values())

        # Reverse lookup for session assignments: ink_idx -> date
        session_ink_to_date = {}
        for d, idx in session.items():
            if d not in api:  # Only session assignments, not API
                session_ink_to_date[idx] = d

        for idx, ink in enumerate(inks):
            brand = ink.get("brand_name", "Unknown")
            name = ink.get("name", "Unknown")
            color = ink.get("color", "#888888")

            # Filter by search query
            if search_query and search_query not in brand.lower() and search_query not in name.lower():
                continue

            # Check if this ink is assigned
            is_session_assigned = idx in session_ink_to_date
            is_api_assigned = idx in assigned_indices and not is_session_assigned

            # Skip API-assigned inks (they can't be moved)
            if is_api_assigned:
                continue

            # Build the item
            session_date = session_ink_to_date.get(idx)
            if session_date:
                date_obj = datetime.strptime(session_date, "%Y-%m-%d")
                date_label = ui.span(
                    f"(assigned to {date_obj.strftime('%b %d')})",
                    class_="ink-picker-date-label"
                )
            else:
                date_label = None

            item = ui.div(
                ui.div(
                    ink_swatch_svg(color, "sm"),
                    class_="ink-picker-swatch"
                ),
                ui.div(
                    ui.span(brand, class_="ink-picker-brand"),
                    ui.span(name, class_="ink-picker-name"),
                    date_label if date_label else "",
                    class_="ink-picker-info"
                ),
                class_="ink-picker-item" + (" ink-picker-item-assigned" if session_date else ""),
                tabindex="0",
                **{
                    "data-ink-idx": str(idx),
                    "data-ink-name": f"{brand} {name}"
                }
            )
            ink_items.append(item)

        if not ink_items:
            return ui.div(
                ui.p("No inks match your search.", class_="ink-picker-no-results"),
                class_="ink-picker-list"
            )

        return ui.div(
            *ink_items,
            class_="ink-picker-list",
            id="ink-picker-list-container"
        )

    # Handler for modal ink selection via click or keyboard
    @reactive.Effect
    @reactive.event(input.ink_picker_select)
    def handle_modal_ink_selection():
        """Auto-assign ink when selection is made in modal."""
        date_str = ink_picker_date.get()
        if not date_str:
            return

        try:
            ink_idx = int(input.ink_picker_select()["ink_idx"])
        except Exception:
            return

        # Use unified move function
        session = session_assignments.get()
        api = api_assignments.get()
        inks = ink_data.get()

        # Check if this ink is already session-assigned (moving it)
        session_ink_to_date = {idx: d for d, idx in session.items() if d not in api}
        from_date = session_ink_to_date.get(ink_idx)

        new_session, result = move_ink_assignment(
            session=session,
            api=api,
            from_date=from_date,
            to_date=date_str,
            ink_idx=ink_idx,
            inks=inks
        )

        if not result.success:
            ui.notification_show(result.message, type="warning", duration=3)
            return

        session_assignments.set(new_session)
        ink_name = result.data.get("ink_name", "ink")
        action = "Moved" if from_date else "Assigned"
        ui.notification_show(f"{action} {ink_name}", type="message", duration=2)

        # Close the modal and reset state
        ui.modal_remove()
        ink_picker_date.set(None)

    # Handler for clicking empty calendar cells
    @reactive.Effect
    @reactive.event(input.calendar_empty_cell_click)
    def handle_empty_cell_click():
        """Show ink picker when empty calendar cell is clicked."""
        click_data = input.calendar_empty_cell_click()
        if not click_data:
            return

        date_str = click_data.get("date")
        if date_str:
            ink_picker_date.set(date_str)
            show_ink_picker_modal(date_str)

    # Drag-and-drop handler for calendar
    @reactive.Effect
    @reactive.event(input.calendar_drag_drop)
    def handle_calendar_drag_drop():
        """Handle drag-and-drop events from the calendar."""
        drag_data = input.calendar_drag_drop()
        if not drag_data:
            return

        from_date = drag_data.get("from_date")
        to_date = drag_data.get("to_date")
        is_swap = drag_data.get("is_swap", False)

        if not from_date or not to_date:
            return

        session = session_assignments.get()
        api = api_assignments.get()
        inks = ink_data.get()

        if is_swap:
            # Target already has an ink - perform swap
            new_session, result = swap_ink_assignments(
                session=session,
                api=api,
                date1=from_date,
                date2=to_date,
                inks=inks
            )
        else:
            # Target is empty - simple move
            new_session, result = move_ink_assignment(
                session=session,
                api=api,
                from_date=from_date,
                to_date=to_date,
                inks=inks
            )

        if result.success:
            session_assignments.set(new_session)
            ui.notification_show(result.message, type="message", duration=2)
        else:
            ui.notification_show(result.message, type="warning", duration=3)

    # Theme editor modal handlers
    @reactive.Effect
    @reactive.event(input.edit_theme)
    def show_theme_editor():
        """Show the theme editor modal for the current month."""
        year = input.year()
        month = current_month.get()
        month_key = f"{year}-{month:02d}"
        month_name = datetime(year, month, 1).strftime("%B %Y")

        # Get existing theme if any
        themes = session_themes.get()
        existing_theme = themes.get(month_key, {})
        current_theme_name = existing_theme.get("theme", "")
        current_theme_desc = existing_theme.get("description", "")

        m = ui.modal(
            ui.input_text(
                "theme_name_input",
                "Theme Name",
                value=current_theme_name,
                placeholder="e.g., Winter Blues, Autumn Warmth"
            ),
            ui.input_text_area(
                "theme_description_input",
                "Description (optional)",
                value=current_theme_desc,
                placeholder="e.g., Cool tones to match the winter sky",
                rows=3
            ),
            title=f"Edit Theme - {month_name}",
            easy_close=True,
            footer=ui.div(
                ui.input_action_button("save_theme", "Save", class_="btn-primary"),
                ui.input_action_button("cancel_theme", "Cancel", class_="btn-secondary"),
                class_="modal-footer-buttons"
            ),
            size="m"
        )
        ui.modal_show(m)

    @reactive.Effect
    @reactive.event(input.save_theme)
    def save_theme_handler():
        """Save the theme from the modal."""
        year = input.year()
        month = current_month.get()
        month_key = f"{year}-{month:02d}"

        theme_name = input.theme_name_input().strip()
        theme_desc = input.theme_description_input().strip()

        if not theme_name:
            ui.notification_show("Theme name is required", type="warning", duration=3)
            return

        # Update session themes
        themes = session_themes.get().copy()
        themes[month_key] = {
            "theme": theme_name,
            "description": theme_desc
        }
        session_themes.set(themes)

        ui.modal_remove()
        ui.notification_show(f"Theme saved for {datetime(year, month, 1).strftime('%B')}",
                            type="message", duration=2)

    @reactive.Effect
    @reactive.event(input.cancel_theme)
    def cancel_theme_handler():
        """Cancel theme editing."""
        ui.modal_remove()

    # Track previous date values for inline date pickers (use dict, not reactive)
    _prev_date_values = {}

    # Dynamic observer for inline date pickers (to change assignment dates)
    @reactive.Effect
    def observe_date_pickers():
        """Set up observers for inline date pickers."""
        year = input.year()
        month = current_month.get()

        # Use isolate to read without creating dependency (prevents infinite loop)
        with reactive.isolate():
            session = session_assignments.get()
            api = api_assignments.get()

        # PHASE 1: Read ALL date inputs to establish reactive dependencies
        input_values = {}
        for date_str in get_month_dates(year, month):
            date_input_id = make_button_id("date", date_str)
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
    
    # Calendar view - delegates to views.py
    def calendar_view():
        return render_calendar_view(
            inks=ink_data.get(),
            daily_assignments=get_daily_assignments(),
            session_assignments=session_assignments.get(),
            api_assignments=api_assignments.get(),
            year=input.year(),
            month=current_month.get(),
            ink_swatch_fn=ink_swatch_svg
        )
    
    # List view - delegates to views.py
    def list_view():
        return render_list_view(
            inks=ink_data.get(),
            daily_assignments=get_daily_assignments(),
            session_assignments=session_assignments.get(),
            api_assignments=api_assignments.get(),
            year=input.year(),
            month=current_month.get(),
            ink_swatch_fn=ink_swatch_svg
        )

    # Ink collection view - delegates to views.py
    @output
    @render.ui
    def ink_collection_view():
        # Explicit dependency to ensure re-render on session changes
        _ = session_assignments.get()

        return render_ink_collection_view(
            inks=ink_data.get(),
            daily_assignments=get_daily_assignments(),
            session_assignments=session_assignments.get(),
            api_assignments=api_assignments.get(),
            year=input.year(),
            search_query=input.ink_search() or "",
            ink_swatch_fn=ink_swatch_svg
        )
    
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

        # Get provider from settings (with default fallback)
        try:
            provider = input.llm_provider()
        except:
            provider = "openai"

        return initialize_chat_session(
            inks=inks,
            year=selected_year.get(),
            provider=provider,
            ink_data_reactive=ink_data,
            selected_year_reactive=selected_year,
            session_assignments_reactive=session_assignments,
            api_assignments_reactive=api_assignments,
            session_themes_reactive=session_themes
        )

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
