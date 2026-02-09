"""
Manual test script for LLM organizer
Run this to test if the LLM integration works with your ink collection
"""
import os
from dotenv import load_dotenv
from api_client import fetch_all_collected_inks
from llm_organizer import get_llm_monthly_assignments
import json

load_dotenv()

# Check for API keys
fpc_token = os.getenv("FPC_API_TOKEN")
anthropic_key = os.getenv("ANTHROPIC_API_KEY")
openai_key = os.getenv("OPENAI_API_KEY")

if not fpc_token:
    print("ERROR: FPC_API_TOKEN not found in .env file")
    exit(1)

if not anthropic_key and not openai_key:
    print("WARNING: No LLM API key found. You need either ANTHROPIC_API_KEY or OPENAI_API_KEY in your .env file")
    print("\nTo get an Anthropic API key:")
    print("1. Go to https://console.anthropic.com/")
    print("2. Create an account or sign in")
    print("3. Go to API Keys section")
    print("4. Create a new key")
    print("5. Add it to your .env file as: ANTHROPIC_API_KEY=your_key_here")
    exit(1)

provider = "anthropic" if anthropic_key else "openai"
print(f"Using provider: {provider}")

print("\n1. Fetching your inks...")
inks = fetch_all_collected_inks(fpc_token)
print(f"✓ Fetched {len(inks)} inks")

print(f"\n2. Asking {provider} for monthly organization suggestions...")
print("   (This may take 30-60 seconds)")

preferences = "May should be all blues and greens. December should have festive reds and greens."

try:
    assignments = get_llm_monthly_assignments(inks, preferences, provider)

    print("\n✓ Received suggestions!")
    print(f"\n{assignments.get('reasoning', 'No reasoning provided')}")

    print("\n3. Monthly Themes:")
    monthly_themes = assignments.get("monthly_themes", {})

    for month in range(1, 13):
        month_data = monthly_themes.get(str(month), {})
        theme = month_data.get("theme", "N/A")
        num_inks = len(month_data.get("ink_indices", []))
        print(f"   {month_data.get('month_name', f'Month {month}'):12} | {theme:30} | {num_inks} inks")

    print("\n✅ LLM organizer is working correctly!")
    print("\nFull response saved to llm_test_output.json")

    with open("llm_test_output.json", "w") as f:
        json.dump(assignments, f, indent=2)

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    print(traceback.format_exc())
