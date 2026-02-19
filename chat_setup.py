"""
Chat initialization helpers for the ink scheduler app.

These functions set up the LLM chat with tools and context.
"""
import traceback

from llm_organizer import create_llm_chat
from chat_tools import create_tool_functions
from app_helpers import get_chat_system_prompt


def initialize_chat_session(
    inks: list[dict],
    year: int,
    provider: str,
    ink_data_reactive,
    selected_year_reactive,
    session_assignments_reactive,
    api_assignments_reactive,
    session_themes_reactive
):
    """
    Initialize a chat session with tools and context.

    Args:
        inks: List of ink dictionaries
        year: Year being organized
        provider: LLM provider ("openai" or "anthropic")
        ink_data_reactive: Reactive value for ink data
        selected_year_reactive: Reactive value for selected year
        session_assignments_reactive: Reactive value for session assignments
        api_assignments_reactive: Reactive value for API assignments
        session_themes_reactive: Reactive value for session themes

    Returns:
        Tuple of (chat_object, snapshot_updater) or None on error
    """
    if not inks:
        return None

    try:
        # Create chat instance with system prompt
        system_message = get_chat_system_prompt(len(inks), year)
        chat_obj = create_llm_chat(provider, system_prompt=system_message)

        # Register tools with session/api assignment state
        tool_functions, snapshot_updater = create_tool_functions(
            ink_data_reactive,
            selected_year_reactive,
            session_assignments_reactive,
            api_assignments_reactive,
            session_themes_reactive
        )
        for tool_func in tool_functions:
            chat_obj.register_tool(tool_func)

        return chat_obj, snapshot_updater

    except Exception as e:
        print(f"Chat initialization error: {traceback.format_exc()}")
        return None
