"""
Test script to verify tool calling is working
"""
import os
from dotenv import load_dotenv
from chatlas import ChatOpenAI
from shiny import reactive

# Load environment
load_dotenv()

# Create mock reactive values
class MockReactive:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        print(f"[REACTIVE UPDATE] Value updated, now has {len(value)} items")
        self._value = value

# Create some test ink data
test_inks = [
    {
        "name": "Blue Velvet",
        "brand_name": "Diamine",
        "cluster_tags": ["blue"],
        "comment": ""
    },
    {
        "name": "Red Dragon",
        "brand_name": "Diamine",
        "cluster_tags": ["red"],
        "comment": ""
    }
]

ink_data = MockReactive(test_inks)
selected_year = MockReactive(2026)
session_assignments = MockReactive({})  # Session assignments (editable)
api_assignments = MockReactive({})  # API assignments (protected/read-only)

# Import tool creation
from chat_tools import create_tool_functions

# Create tools
tools = create_tool_functions(ink_data, selected_year, session_assignments, api_assignments)

# Create chat
chat = ChatOpenAI()

# Register tools
for tool in tools:
    print(f"Registering tool: {tool.__name__}")
    chat.register_tool(tool)

# Test 1: List inks
print("\n" + "="*60)
print("TEST 1: Asking to list inks")
print("="*60)
response = chat.chat("List all my inks", echo="all")
print(f"Response: {response}")

# Test 2: Assign an ink
print("\n" + "="*60)
print("TEST 2: Assign Blue Velvet to Feb 1")
print("="*60)
response = chat.chat("Assign Blue Velvet to 2026-02-01", echo="all")
print(f"Response: {response}")

# Test 3: Check assignments
print("\n" + "="*60)
print("TEST 3: Check February assignments")
print("="*60)
response = chat.chat("What's assigned to February?", echo="all")
print(f"Response: {response}")

# Verify the ink data was actually modified
print("\n" + "="*60)
print("VERIFICATION: Check if ink comment was updated")
print("="*60)
inks = ink_data.get()
for i, ink in enumerate(inks):
    print(f"Ink {i}: {ink['brand_name']} {ink['name']}")
    print(f"  Comment: {ink.get('comment', 'EMPTY')}")
