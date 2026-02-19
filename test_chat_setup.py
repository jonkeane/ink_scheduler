"""
Tests for chat initialization helpers.

These tests verify that initialize_chat_session correctly sets up
the LLM chat with tools and context.
"""
import pytest
from unittest.mock import Mock, patch

from chat_setup import initialize_chat_session


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_inks():
    """Sample ink collection for testing."""
    return [
        {"id": 1, "name": "Kon-Peki", "brand_name": "Iroshizuku", "color": "#007BA7"},
        {"id": 2, "name": "Oxblood", "brand_name": "Diamine", "color": "#800020"},
    ]


@pytest.fixture
def mock_reactive_values():
    """Create mock reactive values."""
    return {
        "ink_data": Mock(),
        "selected_year": Mock(),
        "session_assignments": Mock(),
        "api_assignments": Mock(),
        "session_themes": Mock(),
    }


# =============================================================================
# Tests for initialize_chat_session()
# =============================================================================

class TestInitializeChatSession:
    """Tests for chat session initialization."""

    def test_returns_none_for_empty_inks(self, mock_reactive_values):
        """Should return None when inks list is empty."""
        result = initialize_chat_session(
            inks=[],
            year=2026,
            provider="openai",
            ink_data_reactive=mock_reactive_values["ink_data"],
            selected_year_reactive=mock_reactive_values["selected_year"],
            session_assignments_reactive=mock_reactive_values["session_assignments"],
            api_assignments_reactive=mock_reactive_values["api_assignments"],
            session_themes_reactive=mock_reactive_values["session_themes"],
        )
        assert result is None

    @patch("chat_setup.create_llm_chat")
    @patch("chat_setup.create_tool_functions")
    def test_creates_chat_with_correct_provider(
        self, mock_create_tools, mock_create_chat, sample_inks, mock_reactive_values
    ):
        """Should create chat with specified provider."""
        mock_chat = Mock()
        mock_create_chat.return_value = mock_chat
        mock_create_tools.return_value = ([], Mock())

        initialize_chat_session(
            inks=sample_inks,
            year=2026,
            provider="anthropic",
            ink_data_reactive=mock_reactive_values["ink_data"],
            selected_year_reactive=mock_reactive_values["selected_year"],
            session_assignments_reactive=mock_reactive_values["session_assignments"],
            api_assignments_reactive=mock_reactive_values["api_assignments"],
            session_themes_reactive=mock_reactive_values["session_themes"],
        )

        mock_create_chat.assert_called_once()
        call_args = mock_create_chat.call_args
        assert call_args[0][0] == "anthropic"

    @patch("chat_setup.create_llm_chat")
    @patch("chat_setup.create_tool_functions")
    def test_system_prompt_contains_ink_count(
        self, mock_create_tools, mock_create_chat, sample_inks, mock_reactive_values
    ):
        """System prompt should contain ink count."""
        mock_chat = Mock()
        mock_create_chat.return_value = mock_chat
        mock_create_tools.return_value = ([], Mock())

        initialize_chat_session(
            inks=sample_inks,
            year=2026,
            provider="openai",
            ink_data_reactive=mock_reactive_values["ink_data"],
            selected_year_reactive=mock_reactive_values["selected_year"],
            session_assignments_reactive=mock_reactive_values["session_assignments"],
            api_assignments_reactive=mock_reactive_values["api_assignments"],
            session_themes_reactive=mock_reactive_values["session_themes"],
        )

        call_args = mock_create_chat.call_args
        system_prompt = call_args[1]["system_prompt"]
        assert "2 inks" in system_prompt

    @patch("chat_setup.create_llm_chat")
    @patch("chat_setup.create_tool_functions")
    def test_system_prompt_contains_year(
        self, mock_create_tools, mock_create_chat, sample_inks, mock_reactive_values
    ):
        """System prompt should contain the year."""
        mock_chat = Mock()
        mock_create_chat.return_value = mock_chat
        mock_create_tools.return_value = ([], Mock())

        initialize_chat_session(
            inks=sample_inks,
            year=2026,
            provider="openai",
            ink_data_reactive=mock_reactive_values["ink_data"],
            selected_year_reactive=mock_reactive_values["selected_year"],
            session_assignments_reactive=mock_reactive_values["session_assignments"],
            api_assignments_reactive=mock_reactive_values["api_assignments"],
            session_themes_reactive=mock_reactive_values["session_themes"],
        )

        call_args = mock_create_chat.call_args
        system_prompt = call_args[1]["system_prompt"]
        assert "2026" in system_prompt

    @patch("chat_setup.create_llm_chat")
    @patch("chat_setup.create_tool_functions")
    def test_registers_all_tools(
        self, mock_create_tools, mock_create_chat, sample_inks, mock_reactive_values
    ):
        """Should register all tool functions with the chat."""
        mock_chat = Mock()
        mock_create_chat.return_value = mock_chat
        mock_tool1 = Mock()
        mock_tool2 = Mock()
        mock_create_tools.return_value = ([mock_tool1, mock_tool2], Mock())

        initialize_chat_session(
            inks=sample_inks,
            year=2026,
            provider="openai",
            ink_data_reactive=mock_reactive_values["ink_data"],
            selected_year_reactive=mock_reactive_values["selected_year"],
            session_assignments_reactive=mock_reactive_values["session_assignments"],
            api_assignments_reactive=mock_reactive_values["api_assignments"],
            session_themes_reactive=mock_reactive_values["session_themes"],
        )

        assert mock_chat.register_tool.call_count == 2
        mock_chat.register_tool.assert_any_call(mock_tool1)
        mock_chat.register_tool.assert_any_call(mock_tool2)

    @patch("chat_setup.create_llm_chat")
    @patch("chat_setup.create_tool_functions")
    def test_returns_chat_and_updater_tuple(
        self, mock_create_tools, mock_create_chat, sample_inks, mock_reactive_values
    ):
        """Should return tuple of (chat_obj, snapshot_updater)."""
        mock_chat = Mock()
        mock_updater = Mock()
        mock_create_chat.return_value = mock_chat
        mock_create_tools.return_value = ([], mock_updater)

        result = initialize_chat_session(
            inks=sample_inks,
            year=2026,
            provider="openai",
            ink_data_reactive=mock_reactive_values["ink_data"],
            selected_year_reactive=mock_reactive_values["selected_year"],
            session_assignments_reactive=mock_reactive_values["session_assignments"],
            api_assignments_reactive=mock_reactive_values["api_assignments"],
            session_themes_reactive=mock_reactive_values["session_themes"],
        )

        assert result is not None
        assert len(result) == 2
        assert result[0] is mock_chat
        assert result[1] is mock_updater

    @patch("chat_setup.create_llm_chat")
    @patch("chat_setup.create_tool_functions")
    def test_passes_reactive_values_to_tool_functions(
        self, mock_create_tools, mock_create_chat, sample_inks, mock_reactive_values
    ):
        """Should pass all reactive values to create_tool_functions."""
        mock_chat = Mock()
        mock_create_chat.return_value = mock_chat
        mock_create_tools.return_value = ([], Mock())

        initialize_chat_session(
            inks=sample_inks,
            year=2026,
            provider="openai",
            ink_data_reactive=mock_reactive_values["ink_data"],
            selected_year_reactive=mock_reactive_values["selected_year"],
            session_assignments_reactive=mock_reactive_values["session_assignments"],
            api_assignments_reactive=mock_reactive_values["api_assignments"],
            session_themes_reactive=mock_reactive_values["session_themes"],
        )

        mock_create_tools.assert_called_once_with(
            mock_reactive_values["ink_data"],
            mock_reactive_values["selected_year"],
            mock_reactive_values["session_assignments"],
            mock_reactive_values["api_assignments"],
            mock_reactive_values["session_themes"],
        )

    @patch("chat_setup.create_llm_chat")
    def test_returns_none_on_chat_creation_error(
        self, mock_create_chat, sample_inks, mock_reactive_values
    ):
        """Should return None if chat creation fails."""
        mock_create_chat.side_effect = Exception("API error")

        result = initialize_chat_session(
            inks=sample_inks,
            year=2026,
            provider="openai",
            ink_data_reactive=mock_reactive_values["ink_data"],
            selected_year_reactive=mock_reactive_values["selected_year"],
            session_assignments_reactive=mock_reactive_values["session_assignments"],
            api_assignments_reactive=mock_reactive_values["api_assignments"],
            session_themes_reactive=mock_reactive_values["session_themes"],
        )

        assert result is None

    @patch("chat_setup.create_llm_chat")
    @patch("chat_setup.create_tool_functions")
    def test_returns_none_on_tool_creation_error(
        self, mock_create_tools, mock_create_chat, sample_inks, mock_reactive_values
    ):
        """Should return None if tool creation fails."""
        mock_chat = Mock()
        mock_create_chat.return_value = mock_chat
        mock_create_tools.side_effect = Exception("Tool creation error")

        result = initialize_chat_session(
            inks=sample_inks,
            year=2026,
            provider="openai",
            ink_data_reactive=mock_reactive_values["ink_data"],
            selected_year_reactive=mock_reactive_values["selected_year"],
            session_assignments_reactive=mock_reactive_values["session_assignments"],
            api_assignments_reactive=mock_reactive_values["api_assignments"],
            session_themes_reactive=mock_reactive_values["session_themes"],
        )

        assert result is None


class TestProviderSupport:
    """Tests for different LLM provider support."""

    @patch("chat_setup.create_llm_chat")
    @patch("chat_setup.create_tool_functions")
    def test_openai_provider(
        self, mock_create_tools, mock_create_chat, sample_inks, mock_reactive_values
    ):
        """Should work with openai provider."""
        mock_chat = Mock()
        mock_create_chat.return_value = mock_chat
        mock_create_tools.return_value = ([], Mock())

        result = initialize_chat_session(
            inks=sample_inks,
            year=2026,
            provider="openai",
            ink_data_reactive=mock_reactive_values["ink_data"],
            selected_year_reactive=mock_reactive_values["selected_year"],
            session_assignments_reactive=mock_reactive_values["session_assignments"],
            api_assignments_reactive=mock_reactive_values["api_assignments"],
            session_themes_reactive=mock_reactive_values["session_themes"],
        )

        assert result is not None
        call_args = mock_create_chat.call_args
        assert call_args[0][0] == "openai"
        assert "system_prompt" in call_args[1]
        assert isinstance(call_args[1]["system_prompt"], str)

    @patch("chat_setup.create_llm_chat")
    @patch("chat_setup.create_tool_functions")
    def test_anthropic_provider(
        self, mock_create_tools, mock_create_chat, sample_inks, mock_reactive_values
    ):
        """Should work with anthropic provider."""
        mock_chat = Mock()
        mock_create_chat.return_value = mock_chat
        mock_create_tools.return_value = ([], Mock())

        result = initialize_chat_session(
            inks=sample_inks,
            year=2026,
            provider="anthropic",
            ink_data_reactive=mock_reactive_values["ink_data"],
            selected_year_reactive=mock_reactive_values["selected_year"],
            session_assignments_reactive=mock_reactive_values["session_assignments"],
            api_assignments_reactive=mock_reactive_values["api_assignments"],
            session_themes_reactive=mock_reactive_values["session_themes"],
        )

        assert result is not None
        call_args = mock_create_chat.call_args
        assert call_args[0][0] == "anthropic"

    @patch("chat_setup.create_llm_chat")
    @patch("chat_setup.create_tool_functions")
    def test_google_provider(
        self, mock_create_tools, mock_create_chat, sample_inks, mock_reactive_values
    ):
        """Should work with google provider."""
        mock_chat = Mock()
        mock_create_chat.return_value = mock_chat
        mock_create_tools.return_value = ([], Mock())

        result = initialize_chat_session(
            inks=sample_inks,
            year=2026,
            provider="google",
            ink_data_reactive=mock_reactive_values["ink_data"],
            selected_year_reactive=mock_reactive_values["selected_year"],
            session_assignments_reactive=mock_reactive_values["session_assignments"],
            api_assignments_reactive=mock_reactive_values["api_assignments"],
            session_themes_reactive=mock_reactive_values["session_themes"],
        )

        assert result is not None
        call_args = mock_create_chat.call_args
        assert call_args[0][0] == "google"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
