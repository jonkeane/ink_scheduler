from shiny import App, ui, render, reactive
from datetime import datetime, timedelta
import pandas as pd
from calendar import monthrange
import os
from dotenv import load_dotenv
from assignment_logic import create_yearly_assignments_with_inks, get_month_summary, parse_theme_from_comment
from api_client import fetch_all_collected_inks
from llm_organizer import create_llm_chat, format_all_inks_for_llm
from ink_cache import save_inks_to_cache, load_inks_from_cache, get_cache_info
import traceback

# Load environment variables from .env file
load_dotenv()

# Get API token from environment (if available)
DEFAULT_API_TOKEN = os.getenv("FPC_API_TOKEN", "")

# App UI
app_ui = ui.page_fluid(
    ui.panel_title("Fountain Pen Ink Calendar"),

    ui.layout_sidebar(
        ui.sidebar(
            ui.input_password("api_token", "API Token",
                            value=DEFAULT_API_TOKEN,
                            placeholder="Enter your API token"),
            ui.input_action_button("fetch_inks", "Fetch My Inks", class_="btn-primary", style="width: 100%; margin-bottom: 5px;"),
            ui.input_action_button("clear_token", "Clear Token", class_="btn-secondary", style="width: 100%; margin-bottom: 5px;"),
            ui.output_text("cache_status", inline=True),
            ui.hr(),
            ui.input_select("view_mode", "View Mode",
                          choices=["Calendar View", "List View"],
                          selected="Calendar View"),
            ui.input_numeric("year", "Year", value=datetime.now().year,
                           min=2020, max=2030),
            ui.input_select("month", "Month",
                          choices={str(i): datetime(2000, i, 1).strftime("%B")
                                 for i in range(1, 13)},
                          selected=str(datetime.now().month)),
            ui.input_action_button("randomize", "Randomize Assignments",
                                 class_="btn-secondary"),
            width=300
        ),
        
        ui.navset_tab(
            ui.nav_panel("Ink Calendar",
                ui.output_ui("main_view")
            ),
            ui.nav_panel("Ink Collection",
                ui.output_data_frame("ink_table")
            ),
            ui.nav_panel("Month Assignment",
                ui.output_data_frame("month_assignment")
            ),
            ui.nav_panel("🤖 LLM Organizer",
                ui.div(
                    ui.h3("AI-Powered Ink Organization"),
                    ui.p("Chat with an LLM to organize your inks into monthly themes based on colors, seasons, and your preferences."),
                    ui.input_select("llm_provider",
                                   "LLM Provider",
                                   choices={"openai": "GPT-4 (OpenAI)", "anthropic": "Claude (Anthropic)"},
                                   selected="openai"),
                    ui.input_action_button("reset_chat", "🆕 Reset Chat", class_="btn-secondary btn-sm", style="margin-bottom: 10px;"),
                    ui.hr(),
                    ui.chat_ui("ink_chat"),
                    style="padding: 20px;"
                )
            )
        )
    )
)


def server(input, output, session):
    # Reactive values to store data
    ink_data = reactive.Value([])
    random_seed = reactive.Value(None)  # Seed for randomization
    llm_chat_instance = reactive.Value(None)  # Store LLM chat instance
    chat_initialized = reactive.Value(False)  # Track if chat has been initialized

    # Create Shiny chat interface
    chat = ui.Chat(id="ink_chat", messages=[])

    # Load inks from cache on startup
    @reactive.Effect
    def load_cached_inks():
        cache = load_inks_from_cache()
        if cache:
            inks = cache.get("inks", [])
            ink_data.set(inks)
            ui.notification_show(f"Loaded {len(inks)} inks from cache", type="message", duration=3)
    
    # Cache status display
    @output
    @render.text
    def cache_status():
        info = get_cache_info()
        return info if info else "No cache"

    # Clear API token
    @reactive.Effect
    @reactive.event(input.clear_token)
    def clear_token():
        ui.update_text("api_token", value="")
        ui.notification_show("API token cleared", type="message")

    # Navigate to previous month
    @reactive.Effect
    @reactive.event(input.prev_month)
    def prev_month():
        current_year = input.year()
        current_month = int(input.month())

        if current_month == 1:
            # Go to December of previous year
            ui.update_numeric("year", value=current_year - 1)
            ui.update_select("month", selected="12")
        else:
            # Go to previous month
            ui.update_select("month", selected=str(current_month - 1))

    # Navigate to next month
    @reactive.Effect
    @reactive.event(input.next_month)
    def next_month():
        current_year = input.year()
        current_month = int(input.month())

        if current_month == 12:
            # Go to January of next year
            ui.update_numeric("year", value=current_year + 1)
            ui.update_select("month", selected="1")
        else:
            # Go to next month
            ui.update_select("month", selected=str(current_month + 1))

    # Fetch inks from API with pagination
    @reactive.Effect
    @reactive.event(input.fetch_inks)
    def fetch_inks():
        token = input.api_token()
        if not token:
            ui.notification_show("Please enter an API token", type="error")
            return

        try:
            # Show loading notification
            ui.notification_show("Fetching inks from API...", duration=None, id="fetch_loading", type="message")

            # Fetch all pages of inks
            inks = fetch_all_collected_inks(token)
            ink_data.set(inks)

            # Save to cache
            save_inks_to_cache(inks)

            # Remove loading notification and show success
            ui.notification_remove("fetch_loading")
            ui.notification_show(
                f"Successfully fetched {len(inks)} inks and saved to cache!",
                type="message"
            )
        except Exception as e:
            ui.notification_remove("fetch_loading")
            ui.notification_show(f"Error fetching inks: {str(e)}", type="error")
    
    # Assign inks to every day of the year (no repeats)
    # This is now a reactive calculation that updates when year, ink data, or seed changes
    @reactive.Calc
    def get_yearly_assignments():
        inks = ink_data.get()
        if not inks:
            return {}

        year = input.year()
        seed = random_seed.get()

        # Use the assignment logic that respects explicit date assignments in comments
        assignments = create_yearly_assignments_with_inks(inks, year, seed=seed)

        return assignments
    
    # Randomize yearly assignments
    @reactive.Effect
    @reactive.event(input.randomize)
    def randomize_assignments():
        if not ink_data.get():
            ui.notification_show("Please fetch inks first", type="warning")
            return

        # Change the seed to trigger recalculation with new random assignments
        import random
        random_seed.set(random.randint(0, 1000000))
        ui.notification_show("Ink assignments randomized!", type="message")
    
    # Get daily assignments for the selected month
    @reactive.Calc
    def get_daily_assignments():
        return get_yearly_assignments()
    
    # Main view output
    @output
    @render.ui
    def main_view():
        mode = input.view_mode()
        
        if mode == "Calendar View":
            return calendar_view()
        else:
            return list_view()
    
    # Calendar view
    def calendar_view():
        inks = ink_data.get()
        if not inks:
            return ui.p("No inks loaded. Please fetch your collection first.")

        daily = get_daily_assignments()
        year = input.year()
        month = int(input.month())

        num_days = monthrange(year, month)[1]
        first_weekday = datetime(year, month, 1).weekday()

        # Month/Year title with navigation
        month_name = datetime(year, month, 1).strftime("%B %Y")

        # Get theme from first day of month
        first_day_str = f"{year}-{month:02d}-01"
        first_day_ink_idx = daily.get(first_day_str)
        theme_info = None

        if first_day_ink_idx is not None and first_day_ink_idx < len(inks):
            first_day_ink = inks[first_day_ink_idx]
            comment = first_day_ink.get("comment", "")
            theme_info = parse_theme_from_comment(comment, year)

        # Build title with theme if available
        title_components = [
            ui.input_action_button("prev_month", "← Previous", class_="btn-secondary btn-sm"),
            ui.h2(month_name, style="margin: 0 20px; display: inline-block;"),
            ui.input_action_button("next_month", "Next →", class_="btn-secondary btn-sm"),
        ]

        title_nav = ui.div(
            ui.div(*title_components, style="display: flex; align-items: center; justify-content: center;"),
            style="margin-bottom: 10px;"
        )

        # Add theme display if available
        if theme_info:
            theme_display = ui.div(
                ui.div(
                    ui.strong(theme_info["theme"], style="font-size: 1.2em; color: #333;"),
                    ui.br(),
                    ui.span(theme_info["theme_description"], style="font-size: 0.95em; color: #666; font-style: italic;"),
                    style="text-align: center; padding: 15px; background-color: #f8f9fa; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #007bff;"
                )
            )
        else:
            theme_display = ui.div()

        # Build calendar grid
        weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        # Header row
        header = ui.div(
            *[ui.div(day, style="font-weight: bold; text-align: center; padding: 10px;")
              for day in weekdays],
            style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 5px;"
        )
        
        # Calendar days
        cells = [""] * first_weekday  # Empty cells before first day
        
        for day in range(1, num_days + 1):
            date_str = f"{year}-{month:02d}-{day:02d}"
            ink_idx = daily.get(date_str)
            
            if ink_idx is not None and ink_idx < len(inks):
                ink = inks[ink_idx]
                ink_name = ink.get("name", "Unknown")
                brand = ink.get("brand_name", "")
                ink_color = ink.get("color", "#cccccc")

                # Create a rustic ink swatch with subtle texture
                swatch_style = f"""
                    background: linear-gradient(135deg, {ink_color} 0%, {ink_color}dd 100%);
                    width: 40px;
                    height: 40px;
                    border-radius: 4px;
                    border: 2px solid #8884;
                    box-shadow: 2px 2px 4px rgba(0,0,0,0.2), inset 1px 1px 2px rgba(255,255,255,0.3);
                    margin-bottom: 8px;
                """

                cell_content = ui.div(
                    ui.div(
                        ui.strong(str(day)),
                        style="font-size: 0.9em; margin-bottom: 5px;"
                    ),
                    ui.div(style=swatch_style),
                    ui.span(brand, style="font-size: 0.75em; color: #666; display: block;"),
                    ui.span(ink_name, style="font-size: 0.85em; font-weight: 500; display: block; margin-top: 2px;"),
                    style="border: 1px solid #ddd; padding: 10px; min-height: 120px; background-color: #f9f9f9;"
                )
            else:
                cell_content = ui.div(
                    ui.strong(str(day)),
                    style="border: 1px solid #ddd; padding: 10px; min-height: 100px;"
                )
            
            cells.append(cell_content)
        
        # Fill remaining cells
        while len(cells) % 7 != 0:
            cells.append("")
        
        calendar_grid = ui.div(
            *cells,
            style="display: grid; grid-template-columns: repeat(7, 1fr); gap: 5px;"
        )

        return ui.div(title_nav, theme_display, header, calendar_grid)
    
    # List view
    def list_view():
        inks = ink_data.get()
        if not inks:
            return ui.p("No inks loaded. Please fetch your collection first.")

        daily = get_daily_assignments()
        year = input.year()
        month = int(input.month())
        
        rows = []
        num_days = monthrange(year, month)[1]
        
        for day in range(1, num_days + 1):
            date_str = f"{year}-{month:02d}-{day:02d}"
            ink_idx = daily.get(date_str)
            
            if ink_idx is not None and ink_idx < len(inks):
                ink = inks[ink_idx]
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                
                row = ui.div(
                    ui.div(
                        ui.strong(date_obj.strftime("%A, %B %d, %Y")),
                        style="font-size: 1.1em;"
                    ),
                    ui.div(
                        f"{ink.get('brand_name', 'Unknown')} - {ink.get('name', 'Unknown')}",
                        style="margin-left: 20px; color: #555;"
                    ),
                    style="padding: 15px; border-bottom: 1px solid #eee;"
                )
                rows.append(row)
        
        return ui.div(*rows, style="max-height: 800px; overflow-y: auto;")
    
    # Ink collection table
    @output
    @render.data_frame
    def ink_table():
        inks = ink_data.get()
        if not inks:
            return pd.DataFrame()
        
        df = pd.DataFrame([
            {
                "Brand": ink.get("brand_name", ""),
                "Name": ink.get("name", ""),
                "Color": ink.get("color", ""),
                "Type": ink.get("kind", "")
            }
            for ink in inks
        ])
        
        return render.DataGrid(df, width="100%")
    
    # Month assignment table
    @output
    @render.data_frame
    def month_assignment():
        inks = ink_data.get()
        assignments = get_yearly_assignments()
        year = input.year()

        if not inks or not assignments:
            return pd.DataFrame()

        # Group assignments by month using tested function
        rows = []
        for month_num in range(1, 13):
            month_name = datetime(2000, month_num, 1).strftime("%B")
            ink_indices = get_month_summary(assignments, year, month_num)
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

    # Initialize chat with ink data
    def initialize_chat():
        """Initialize the LLM chat with ink collection context."""
        inks = ink_data.get()
        if not inks:
            return None

        provider = input.llm_provider()

        try:
            # Create chat instance
            ink_summary = format_all_inks_for_llm(inks)
            system_message = f"""You are an expert fountain pen ink curator helping organize {len(inks)} inks into monthly themes.

{ink_summary}

Help the user organize their inks by:
- Suggesting monthly themes based on colors, seasons, and moods
- Explaining your reasoning
- Being flexible and iterative based on their feedback
- Asking clarifying questions when needed"""
            
            chat_obj = create_llm_chat(provider, system_prompt=system_message)

            return chat_obj

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

            chat_obj = initialize_chat()
            if not chat_obj:
                await chat.append_message("❌ Error initializing chat. Please check your API key in the .env file.")
                return

            llm_chat_instance.set(chat_obj)
            chat_initialized.set(True)

            # Send welcome message
            await chat.append_message("Hello! I've reviewed your ink collection and I'm ready to help you organize it into monthly themes. What are you thinking for your yearly ink schedule?")
            return

        # Get response from LLM
        chat_obj = llm_chat_instance.get()
        if not chat_obj:
            await chat.append_message("❌ Chat not initialized. Please reset and try again.")
            return

        try:
            # Use stream() to avoid display issues - collect all chunks
            chunks = []
            for chunk in chat_obj.stream(user_input):
                chunks.append(chunk)
            
            # Combine chunks into full response
            response_text = "".join(str(chunk) for chunk in chunks)
            await chat.append_message(response_text)

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
