"""
LLM-powered ink organizer using chatlas
"""
from typing import List, Dict, Optional
import json
from chatlas import ChatAnthropic, ChatOpenAI
import anthropic
import openai
import os


# Fallback models if API call fails
DEFAULT_MODELS = {
    "anthropic": [
        "claude-sonnet-4-20250514",
        "claude-opus-4-20250514",
        "claude-3-5-haiku-20241022",
    ],
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "o1",
        "o1-mini",
    ],
}


def list_available_models(provider: str) -> list[str]:
    """
    Fetch available models from the provider's API.

    Args:
        provider: "anthropic" or "openai"

    Returns:
        List of model IDs available for the provider
    """
    try:
        if provider == "anthropic":
            client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY
            response = client.models.list()
            models = [m.id for m in response.data]
            # Sort to put claude-4 models first, then claude-3
            models.sort(key=lambda x: (not x.startswith("claude-sonnet-4"),
                                        not x.startswith("claude-opus-4"),
                                        x))
            return models if models else DEFAULT_MODELS["anthropic"]
        elif provider == "openai":
            client = openai.OpenAI()  # Uses OPENAI_API_KEY
            response = client.models.list()
            # Filter to chat-capable models
            models = [m.id for m in response.data
                      if m.id.startswith(("gpt-4", "gpt-3.5", "o1", "o3"))]
            models.sort(reverse=True)  # Newer models first
            return models if models else DEFAULT_MODELS["openai"]
        else:
            return []
    except Exception as e:
        print(f"Error fetching models for {provider}: {e}")
        return DEFAULT_MODELS.get(provider, [])


def format_ink_for_llm(ink: Dict, idx: int) -> str:
    """Format a single ink's data for LLM consumption."""
    parts = [
        f"Ink #{idx}:",
        f"  Brand: {ink.get('brand_name', 'Unknown')}",
        f"  Name: {ink.get('name', 'Unknown')}",
        f"  Color: {ink.get('color', 'N/A')}",
    ]

    if ink.get('line_name'):
        parts.append(f"  Line: {ink.get('line_name')}")

    if ink.get('cluster_tags'):
        tags = ', '.join(ink.get('cluster_tags', []))
        parts.append(f"  Color Tags: {tags}")

    if ink.get('comment'):
        parts.append(f"  Description: {ink.get('comment')}")

    if ink.get('kind'):
        parts.append(f"  Type: {ink.get('kind')}")

    if ink.get('used'):
        parts.append(f"  Previously Used: Yes")

    return '\n'.join(parts)


def format_all_inks_for_llm(inks: List[Dict]) -> str:
    """Format all inks into a comprehensive summary for the LLM."""
    ink_list = '\n\n'.join([format_ink_for_llm(ink, idx) for idx, ink in enumerate(inks)])

    # Add summary statistics
    total = len(inks)
    colors = {}
    for ink in inks:
        for tag in ink.get('cluster_tags', []):
            colors[tag] = colors.get(tag, 0) + 1

    summary = f"""
# Ink Collection Summary

Total Inks: {total}

Color Distribution:
{chr(10).join([f"  - {color}: {count} inks" for color, count in sorted(colors.items(), key=lambda x: -x[1])[:15]])}

# Complete Ink List

{ink_list}
"""
    return summary


def create_llm_chat(provider: str = "anthropic", model: Optional[str] = None, system_prompt: Optional[str] = None):
    """
    Create a chatlas chat instance.

    Args:
        provider: "anthropic" or "openai"
        model: Optional specific model name
        system_prompt: Optional system prompt to initialize the chat

    Returns:
        Chat instance
    """
    if provider == "anthropic":
        # Uses ANTHROPIC_API_KEY from environment
        return ChatAnthropic(model=model or "claude-sonnet-4-20250514", system_prompt=system_prompt)
    elif provider == "openai":
        # Uses OPENAI_API_KEY from environment
        return ChatOpenAI(model=model or "gpt-4o", system_prompt=system_prompt)
    else:
        raise ValueError(f"Unknown provider: {provider}")


def ask_llm_for_monthly_themes(inks: List[Dict], user_preferences: Optional[str] = None, provider: str = "anthropic") -> str:
    """
    Ask an LLM to suggest monthly themes and ink assignments.

    Args:
        inks: List of ink dictionaries
        user_preferences: Optional user preferences (e.g., "May should be all blues")
        provider: LLM provider to use

    Returns:
        LLM's response as a string
    """
    ink_data = format_all_inks_for_llm(inks)

    system_prompt = """You are an expert fountain pen ink curator and organizer. Your job is to help users organize their ink collection into meaningful monthly themes.

When analyzing an ink collection, consider:
- Color families and harmonies
- Seasonal appropriateness (e.g., warm colors in fall, pastels in spring)
- Ink properties (shimmer, sheen, special effects)
- User preferences and stated requirements
- Variety and balance across the year

You should output your recommendations in a structured JSON format."""

    user_prompt = f"""{ink_data}

Please analyze this ink collection and suggest a yearly organization scheme with monthly themes.

"""

    if user_preferences:
        user_prompt += f"""
User Preferences:
{user_preferences}

Please incorporate these preferences into your suggestions.
"""

    user_prompt += """
Provide your response as JSON in the following format:

{
  "monthly_themes": {
    "1": {
      "month_name": "January",
      "theme": "Theme Name",
      "theme_description": "Detailed description of why this theme works for this month",
      "ink_indices": [0, 5, 12, ...]
    },
    ... (repeat for months 2-12)
  },
  "reasoning": "Overall explanation of your organization strategy"
}

Make sure:
1. Every ink is assigned to exactly one month (no repeats, no omissions)
2. Each month gets roughly equal numbers of inks (within reason)
3. Themes are coherent and meaningful
4. You explain your reasoning clearly

Return ONLY the JSON, no other text."""

    chat = create_llm_chat(provider)

    # Combine system prompt with user prompt
    combined_prompt = f"""{system_prompt}

---

{user_prompt}"""

    response = chat.chat(combined_prompt)

    return response.content


def parse_llm_monthly_assignments(llm_response: str) -> Dict:
    """
    Parse the LLM's JSON response into monthly assignments.

    Args:
        llm_response: Raw LLM response string

    Returns:
        Dictionary with monthly_themes and reasoning
    """
    # Try to extract JSON from the response
    llm_response = llm_response.strip()

    # Remove markdown code blocks if present
    if llm_response.startswith("```json"):
        llm_response = llm_response[7:]
    if llm_response.startswith("```"):
        llm_response = llm_response[3:]
    if llm_response.endswith("```"):
        llm_response = llm_response[:-3]

    llm_response = llm_response.strip()

    try:
        data = json.loads(llm_response)
        return data
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM response as JSON: {e}\n\nResponse was:\n{llm_response}")


def validate_monthly_assignments(assignments: Dict, num_inks: int) -> List[str]:
    """
    Validate that the LLM's assignments are valid.

    Args:
        assignments: Parsed LLM assignments
        num_inks: Total number of inks

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    monthly_themes = assignments.get("monthly_themes", {})

    # Check all months are present
    for month in range(1, 13):
        if str(month) not in monthly_themes:
            errors.append(f"Missing assignments for month {month}")

    # Check all inks are assigned exactly once
    all_assigned_inks = set()
    for month, data in monthly_themes.items():
        ink_indices = data.get("ink_indices", [])
        for idx in ink_indices:
            if idx in all_assigned_inks:
                errors.append(f"Ink {idx} is assigned to multiple months")
            all_assigned_inks.add(idx)

    # Check all inks are assigned
    expected_inks = set(range(num_inks))
    missing_inks = expected_inks - all_assigned_inks
    if missing_inks:
        errors.append(f"Inks not assigned: {sorted(missing_inks)}")

    extra_inks = all_assigned_inks - expected_inks
    if extra_inks:
        errors.append(f"Invalid ink indices: {sorted(extra_inks)}")

    return errors
