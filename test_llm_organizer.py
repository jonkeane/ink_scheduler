"""
Tests for llm_organizer.py - LLM integration and response parsing functions.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import json

from llm_organizer import (
    format_ink_for_llm,
    format_all_inks_for_llm,
    create_llm_chat,
    ask_llm_for_monthly_themes,
    parse_llm_monthly_assignments,
    validate_monthly_assignments
)


# =============================================================================
# Tests for format_ink_for_llm()
# =============================================================================

class TestFormatInkForLlm:
    """Tests for format_ink_for_llm function."""

    def test_complete_ink_data(self, sample_inks):
        """Test formatting ink with all fields populated."""
        ink = sample_inks[0]  # Diamine Blue Velvet
        result = format_ink_for_llm(ink, 0)

        assert "Ink #0:" in result
        assert "Brand: Diamine" in result
        assert "Name: Blue Velvet" in result
        assert "Color: #1a237e" in result
        assert "Line: Standard" in result
        assert "Color Tags: blue, dark" in result
        assert "Description: A beautiful deep blue" in result
        assert "Type: fountain pen ink" in result
        assert "Previously Used: Yes" in result

    def test_minimal_ink_data(self, sample_inks_minimal):
        """Test formatting ink with only required fields."""
        ink = sample_inks_minimal[0]
        result = format_ink_for_llm(ink, 5)

        assert "Ink #5:" in result
        assert "Brand: Test Brand" in result
        assert "Name: Test Ink" in result
        # Should not contain optional fields
        assert "Line:" not in result
        assert "Color Tags:" not in result
        assert "Description:" not in result
        assert "Type:" not in result
        assert "Previously Used:" not in result

    def test_missing_optional_fields(self):
        """Test ink with some optional fields missing."""
        ink = {
            "brand_name": "Test",
            "name": "Ink",
            "color": "#000000",
            "line_name": "",  # Empty string
            "cluster_tags": [],  # Empty list
            "kind": "ink"
        }
        result = format_ink_for_llm(ink, 10)

        assert "Ink #10:" in result
        assert "Brand: Test" in result
        # Empty line_name should not appear
        assert "Line:" not in result
        # Empty cluster_tags should not appear
        assert "Color Tags:" not in result
        # Kind should appear
        assert "Type: ink" in result

    def test_empty_none_values(self):
        """Test ink with None values - function uses .get() default only for missing keys."""
        ink = {
            "brand_name": None,
            "name": None,
            "color": None
        }
        result = format_ink_for_llm(ink, 0)

        # Note: .get() only uses default when key is missing, not when value is None
        # So None values are passed through as "None"
        assert "Brand: None" in result
        assert "Name: None" in result
        assert "Color: None" in result

    def test_missing_keys_use_defaults(self):
        """Test that missing keys use default values."""
        ink = {}  # Empty dict - all keys missing
        result = format_ink_for_llm(ink, 0)

        # When keys are missing, defaults are used
        assert "Brand: Unknown" in result
        assert "Name: Unknown" in result
        assert "Color: N/A" in result

    def test_output_format_structure(self, sample_inks):
        """Test that output has correct line structure."""
        ink = sample_inks[0]
        result = format_ink_for_llm(ink, 0)

        lines = result.split("\n")
        # First line should be "Ink #N:"
        assert lines[0] == "Ink #0:"
        # Other lines should be indented with 2 spaces
        for line in lines[1:]:
            if line:  # Skip empty lines
                assert line.startswith("  ")


# =============================================================================
# Tests for format_all_inks_for_llm()
# =============================================================================

class TestFormatAllInksForLlm:
    """Tests for format_all_inks_for_llm function."""

    def test_empty_list(self):
        """Test formatting empty ink list."""
        result = format_all_inks_for_llm([])

        assert "Total Inks: 0" in result
        assert "# Ink Collection Summary" in result

    def test_single_ink(self, sample_inks):
        """Test formatting single ink."""
        result = format_all_inks_for_llm([sample_inks[0]])

        assert "Total Inks: 1" in result
        assert "Ink #0:" in result
        assert "Diamine" in result

    def test_multiple_inks_numbering(self, sample_inks):
        """Test that multiple inks are numbered correctly."""
        result = format_all_inks_for_llm(sample_inks)

        assert "Total Inks: 5" in result
        assert "Ink #0:" in result
        assert "Ink #1:" in result
        assert "Ink #2:" in result
        assert "Ink #3:" in result
        assert "Ink #4:" in result

    def test_color_distribution_calculation(self, sample_inks):
        """Test that color distribution is calculated correctly."""
        result = format_all_inks_for_llm(sample_inks)

        assert "Color Distribution:" in result
        # Blue appears in 2 inks, dark in 2, teal in 2
        assert "blue: 2 inks" in result
        assert "dark: 2 inks" in result

    def test_summary_statistics_formatting(self, sample_inks):
        """Test that summary section is properly formatted."""
        result = format_all_inks_for_llm(sample_inks)

        assert "# Ink Collection Summary" in result
        assert "# Complete Ink List" in result
        assert "Total Inks:" in result
        assert "Color Distribution:" in result


# =============================================================================
# Tests for create_llm_chat()
# =============================================================================

class TestCreateLlmChat:
    """Tests for create_llm_chat function."""

    @patch('llm_organizer.ChatAnthropic')
    def test_anthropic_default_model(self, mock_anthropic):
        """Test creating Anthropic chat with default model."""
        mock_instance = Mock()
        mock_anthropic.return_value = mock_instance

        result = create_llm_chat("anthropic")

        mock_anthropic.assert_called_once_with(
            model="claude-sonnet-4-20250514",
            system_prompt=None
        )
        assert result == mock_instance

    @patch('llm_organizer.ChatOpenAI')
    def test_openai_default_model(self, mock_openai):
        """Test creating OpenAI chat with default model."""
        mock_instance = Mock()
        mock_openai.return_value = mock_instance

        result = create_llm_chat("openai")

        mock_openai.assert_called_once_with(
            model="gpt-4o",
            system_prompt=None
        )
        assert result == mock_instance

    @patch('llm_organizer.ChatAnthropic')
    def test_custom_model_name(self, mock_anthropic):
        """Test creating chat with custom model name."""
        mock_instance = Mock()
        mock_anthropic.return_value = mock_instance

        result = create_llm_chat("anthropic", model="claude-3-opus")

        mock_anthropic.assert_called_once_with(
            model="claude-3-opus",
            system_prompt=None
        )

    @patch('llm_organizer.ChatAnthropic')
    def test_with_system_prompt(self, mock_anthropic):
        """Test creating chat with system prompt."""
        mock_instance = Mock()
        mock_anthropic.return_value = mock_instance

        result = create_llm_chat("anthropic", system_prompt="You are helpful.")

        mock_anthropic.assert_called_once_with(
            model="claude-sonnet-4-20250514",
            system_prompt="You are helpful."
        )

    def test_invalid_provider_raises_error(self):
        """Test that invalid provider raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            create_llm_chat("invalid_provider")

        assert "Unknown provider: invalid_provider" in str(exc_info.value)

    @patch('llm_organizer.ChatOpenAI')
    def test_openai_with_custom_model(self, mock_openai):
        """Test OpenAI with custom model."""
        mock_instance = Mock()
        mock_openai.return_value = mock_instance

        result = create_llm_chat("openai", model="gpt-4-turbo")

        mock_openai.assert_called_once_with(
            model="gpt-4-turbo",
            system_prompt=None
        )


# =============================================================================
# Tests for ask_llm_for_monthly_themes()
# =============================================================================

class TestAskLlmForMonthlyThemes:
    """Tests for ask_llm_for_monthly_themes function."""

    @patch('llm_organizer.create_llm_chat')
    def test_with_sample_inks(self, mock_create_chat, sample_inks):
        """Test asking for themes with sample ink data."""
        mock_chat = Mock()
        mock_response = Mock()
        mock_response.content = '{"monthly_themes": {}}'
        mock_chat.chat.return_value = mock_response
        mock_create_chat.return_value = mock_chat

        result = ask_llm_for_monthly_themes(sample_inks)

        assert result == '{"monthly_themes": {}}'
        mock_create_chat.assert_called_once_with("anthropic")
        mock_chat.chat.assert_called_once()
        # Verify prompt contains ink data
        call_args = mock_chat.chat.call_args[0][0]
        assert "Total Inks: 5" in call_args

    @patch('llm_organizer.create_llm_chat')
    def test_with_user_preferences(self, mock_create_chat, sample_inks):
        """Test that user preferences are included in prompt."""
        mock_chat = Mock()
        mock_response = Mock()
        mock_response.content = '{}'
        mock_chat.chat.return_value = mock_response
        mock_create_chat.return_value = mock_chat

        ask_llm_for_monthly_themes(sample_inks, user_preferences="May should be all blues")

        call_args = mock_chat.chat.call_args[0][0]
        assert "May should be all blues" in call_args
        assert "User Preferences:" in call_args

    @patch('llm_organizer.create_llm_chat')
    def test_without_user_preferences(self, mock_create_chat, sample_inks):
        """Test prompt without user preferences."""
        mock_chat = Mock()
        mock_response = Mock()
        mock_response.content = '{}'
        mock_chat.chat.return_value = mock_response
        mock_create_chat.return_value = mock_chat

        ask_llm_for_monthly_themes(sample_inks)

        call_args = mock_chat.chat.call_args[0][0]
        assert "User Preferences:" not in call_args

    @patch('llm_organizer.create_llm_chat')
    def test_different_providers(self, mock_create_chat, sample_inks):
        """Test with different LLM providers."""
        mock_chat = Mock()
        mock_response = Mock()
        mock_response.content = '{}'
        mock_chat.chat.return_value = mock_response
        mock_create_chat.return_value = mock_chat

        ask_llm_for_monthly_themes(sample_inks, provider="openai")

        mock_create_chat.assert_called_once_with("openai")

    @patch('llm_organizer.create_llm_chat')
    def test_empty_ink_list(self, mock_create_chat):
        """Test with empty ink list."""
        mock_chat = Mock()
        mock_response = Mock()
        mock_response.content = '{}'
        mock_chat.chat.return_value = mock_response
        mock_create_chat.return_value = mock_chat

        result = ask_llm_for_monthly_themes([])

        call_args = mock_chat.chat.call_args[0][0]
        assert "Total Inks: 0" in call_args


# =============================================================================
# Tests for parse_llm_monthly_assignments()
# =============================================================================

class TestParseLlmMonthlyAssignments:
    """Tests for parse_llm_monthly_assignments function."""

    def test_valid_json(self, mock_llm_response):
        """Test parsing valid JSON response."""
        result = parse_llm_monthly_assignments(mock_llm_response)

        assert "monthly_themes" in result
        assert "1" in result["monthly_themes"]
        assert result["monthly_themes"]["1"]["theme"] == "Winter Blues"
        assert "reasoning" in result

    def test_json_in_code_block(self, mock_llm_response):
        """Test parsing JSON wrapped in ```json code blocks."""
        wrapped = f"```json\n{mock_llm_response}\n```"
        result = parse_llm_monthly_assignments(wrapped)

        assert "monthly_themes" in result

    def test_json_in_plain_code_block(self, mock_llm_response):
        """Test parsing JSON wrapped in plain ``` code blocks."""
        wrapped = f"```\n{mock_llm_response}\n```"
        result = parse_llm_monthly_assignments(wrapped)

        assert "monthly_themes" in result

    def test_invalid_json_raises_error(self):
        """Test that invalid JSON raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            parse_llm_monthly_assignments("not valid json")

        assert "Failed to parse LLM response as JSON" in str(exc_info.value)

    def test_whitespace_handling(self, mock_llm_response):
        """Test that leading/trailing whitespace is handled."""
        with_whitespace = f"\n\n  {mock_llm_response}  \n\n"
        result = parse_llm_monthly_assignments(with_whitespace)

        assert "monthly_themes" in result


# =============================================================================
# Tests for validate_monthly_assignments()
# =============================================================================

class TestValidateMonthlyAssignments:
    """Tests for validate_monthly_assignments function."""

    def test_valid_assignments(self):
        """Test validation of correct assignments."""
        assignments = {
            "monthly_themes": {
                str(m): {"ink_indices": [i]} for m, i in zip(range(1, 13), range(12))
            }
        }
        errors = validate_monthly_assignments(assignments, 12)
        assert errors == []

    def test_missing_months(self):
        """Test detection of missing months."""
        assignments = {
            "monthly_themes": {
                "1": {"ink_indices": [0]},
                "2": {"ink_indices": [1]}
                # Missing months 3-12
            }
        }
        errors = validate_monthly_assignments(assignments, 2)

        assert any("Missing assignments for month 3" in e for e in errors)

    def test_duplicate_ink_assignments(self):
        """Test detection of duplicate ink assignments."""
        assignments = {
            "monthly_themes": {
                str(m): {"ink_indices": [0]} for m in range(1, 13)  # Ink 0 assigned 12 times
            }
        }
        errors = validate_monthly_assignments(assignments, 1)

        assert any("assigned to multiple months" in e for e in errors)

    def test_missing_inks(self):
        """Test detection of inks not assigned."""
        assignments = {
            "monthly_themes": {
                str(m): {"ink_indices": []} for m in range(1, 13)  # No inks assigned
            }
        }
        errors = validate_monthly_assignments(assignments, 5)

        assert any("Inks not assigned" in e for e in errors)
        assert any("[0, 1, 2, 3, 4]" in e for e in errors)

    def test_invalid_ink_indices(self):
        """Test detection of out-of-range ink indices."""
        assignments = {
            "monthly_themes": {
                str(m): {"ink_indices": [100]} for m in range(1, 13)  # Invalid index
            }
        }
        errors = validate_monthly_assignments(assignments, 5)

        assert any("Invalid ink indices" in e for e in errors)

    def test_empty_assignments(self):
        """Test validation of empty assignments."""
        assignments = {"monthly_themes": {}}
        errors = validate_monthly_assignments(assignments, 5)

        # Should report all months as missing
        assert len(errors) >= 12

    def test_num_inks_zero(self):
        """Test validation with num_inks=0."""
        assignments = {
            "monthly_themes": {
                str(m): {"ink_indices": []} for m in range(1, 13)
            }
        }
        errors = validate_monthly_assignments(assignments, 0)

        # With 0 inks, empty assignments should be valid
        assert errors == []

    def test_all_inks_assigned_once(self):
        """Test that all inks assigned exactly once passes validation."""
        # 5 inks distributed across months
        assignments = {
            "monthly_themes": {
                "1": {"ink_indices": [0]},
                "2": {"ink_indices": [1]},
                "3": {"ink_indices": [2]},
                "4": {"ink_indices": [3]},
                "5": {"ink_indices": [4]},
                "6": {"ink_indices": []},
                "7": {"ink_indices": []},
                "8": {"ink_indices": []},
                "9": {"ink_indices": []},
                "10": {"ink_indices": []},
                "11": {"ink_indices": []},
                "12": {"ink_indices": []}
            }
        }
        errors = validate_monthly_assignments(assignments, 5)
        assert errors == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
