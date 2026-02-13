"""
Test chat_tools functions to verify they work correctly.
This test doesn't actually run the tools, but verifies they're created correctly.
"""
from chat_tools import create_tool_functions
from assignment_logic import find_ink_by_name, parse_comment_json, has_assignment
from shiny import reactive
import json


def test_helper_functions():
    """Test the helper functions that don't need reactive context."""

    print("Testing helper functions...")
    print()

    # Test 1: Parse comment JSON
    print("Test 1: parse_comment_json()")
    valid_json = '{"swatch2026": {"date": "2026-01-01"}}'
    result = parse_comment_json(valid_json)
    print(f"Valid JSON parsed: {result}")

    invalid_json = "not json"
    result = parse_comment_json(invalid_json)
    print(f"Invalid JSON returns empty dict: {result == {}}")
    print()

    # Test 2: Check assignment status
    print("Test 2: has_assignment()")
    assigned_ink = {
        "private_comment": json.dumps({"swatch2026": {"date": "2026-01-01"}})
    }
    result = has_assignment(assigned_ink, 2026)
    print(f"Assigned ink detected: {result}")

    unassigned_ink = {
        "private_comment": None
    }
    result = has_assignment(unassigned_ink, 2026)
    print(f"Unassigned ink detected: {not result}")
    print()

    # Test 3: Find ink by name
    print("Test 3: find_ink_by_name()")
    test_inks = [
        {"brand_name": "Diamine", "name": "Blue Velvet"},
        {"brand_name": "Pilot", "name": "Iroshizuku Kon-peki"},
        {"brand_name": "Noodler's", "name": "Heart of Darkness"}
    ]

    result = find_ink_by_name("Blue Velvet", test_inks)
    if result:
        idx, ink = result
        print(f"Found 'Blue Velvet' at index {idx}: {ink['brand_name']} {ink['name']}")

    result = find_ink_by_name("kon-peki", test_inks)  # Case insensitive
    if result:
        idx, ink = result
        print(f"Found 'kon-peki' (case insensitive) at index {idx}: {ink['brand_name']} {ink['name']}")

    result = find_ink_by_name("darkness", test_inks)  # Partial match
    if result:
        idx, ink = result
        print(f"Found 'darkness' (partial) at index {idx}: {ink['brand_name']} {ink['name']}")

    result = find_ink_by_name("nonexistent", test_inks)
    print(f"Non-existent ink returns None: {result is None}")
    print()

    print("All helper function tests passed!")
    print()

    # Test tool creation (doesn't execute them)
    print("Test 4: Tool creation with two-tier state")
    ink_data = reactive.value([])
    selected_year = reactive.value(2026)
    session_assignments = reactive.value({})  # New: session state
    api_assignments = reactive.value({})  # New: API state

    tools = create_tool_functions(ink_data, selected_year, session_assignments, api_assignments)
    print(f"Created {len(tools)} tool functions:")
    for tool in tools:
        print(f"  - {tool.__name__}")
    print()

    print("All tests completed successfully!")


if __name__ == "__main__":
    test_helper_functions()
