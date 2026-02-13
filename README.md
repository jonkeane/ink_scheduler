# Fountain Pen Ink Calendar Scheduler

A Python Shiny web application that creates a personalized ink calendar by assigning each of your fountain pen inks to unique days throughout the year.

## Features

- 📅 **Yearly Calendar View** - Visualize your ink assignments across the entire year
- 🎨 **Color Swatches** - See each ink's color displayed as a rustic swatch
- 🔀 **Random Assignment** - Automatically distribute inks across days with no repeats
- 📌 **Manual Date Assignment** - Pin specific inks to specific dates using comments
- 💬 **AI Chat Interface** - Interactive conversation with Claude or GPT-4 to organize your inks
- 💾 **Disk Caching** - Your ink collection is cached locally, no need to re-fetch on every restart
- 🔄 **Easy Navigation** - Browse months with previous/next buttons
- 🔑 **Environment Variables** - Save your API tokens locally
- ✅ **Fully Tested** - 33 passing tests covering all core functionality

## Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file with your API token:
   ```bash
   FPC_API_TOKEN=your_token_here
   ```

3. Run the app:
   ```bash
   shiny run app.py
   ```

## Disk Cache

Your ink collection is automatically cached to disk after fetching from the API. Benefits:

- **Fast Startup** - Loads from cache instantly on app restart
- **Reduced API Calls** - No need to re-fetch every time
- **Offline Work** - Continue using the app even without internet

The cache is stored in `ink_cache.json`. To refresh your collection from the API, simply click "Fetch My Inks" again.

## How to Assign Inks to Specific Dates with Themes

You can manually assign any ink to a specific date and add monthly themes by adding JSON to the ink's comment field on Fountain Pen Companion:

### Format

```json
{
  "swatch2026": {
    "theme": "All samples",
    "theme_description": "New inks for a new year. Many samples from new friends.",
    "date": "2026-01-01"
  }
}
```

- **Key**: `swatch` + the 4-digit year (e.g., `swatch2026`, `swatch2027`)
- **Value**: Object containing:
  - `date`: Date in `YYYY-MM-DD` format (required)
  - `theme`: Short theme name (optional, displayed prominently)
  - `theme_description`: Longer theme description (optional, displayed as subtitle)

### Examples

**Pin an ink to New Year's Day 2026 with a theme:**
```json
{
  "swatch2026": {
    "theme": "New Year Celebration",
    "theme_description": "Starting the year with festive inks",
    "date": "2026-01-01"
  }
}
```

**Pin an ink without a theme:**
```json
{
  "swatch2026": {
    "date": "2026-05-15"
  }
}
```

**Pin inks for multiple years:**
```json
{
  "swatch2026": {"date": "2026-03-20", "theme": "Spring"},
  "swatch2027": {"date": "2027-03-20", "theme": "Spring"}
}
```

### Theme Display

The app displays the theme from the **first day of each month**. If the ink assigned to the first day has a theme in its comment, it will be shown at the top of the calendar for that month.

### How It Works

1. The app reads the `comment` field from each ink via the API
2. It parses any JSON and looks for `swatchYYYY` keys matching the selected year
3. Inks with explicit date assignments are placed on those specific days first
4. All remaining inks are randomly distributed across remaining days
5. Every ink gets assigned to exactly one day (no repeats!)
6. The theme from the first day's ink is displayed at the top of each month's calendar

### Backward Compatibility

The app still supports the old simple format for users who don't want themes:
```json
{"swatch2026": "2026-01-01"}
```

This will work exactly as before - the ink gets assigned to that date with no theme displayed.

### Priority

If two inks claim the same date, the first one processed gets it. The second ink will be randomly assigned to a different day.

## AI-Powered Organization (Chat Interface)

The app includes an interactive chat interface where you can have a conversation with an AI to organize your inks. The AI can now **actively manage your ink assignments** using tools!

### Features

- **Natural Conversation** - Chat back and forth with Claude or GPT-4
- **Active Assignment Management** - AI can search inks, view assignments, and assign inks to dates
- **Protected Assignments** - Inks already assigned via comments are protected and won't be changed
- **Tool-Based Actions** - AI uses functions to read and modify your ink calendar
- **Visual History** - See the entire conversation thread

### Available AI Tools

The AI assistant has access to these tools:

1. **list_all_inks()** - Browse your complete collection with assignment status
2. **search_inks(query, color, brand)** - Find specific inks by name, color, or brand
3. **get_month_assignments(month, year)** - View what's assigned to a specific month
4. **assign_ink_to_date(ink_name, date, theme, theme_description)** - Assign an ink to a specific date
5. **bulk_assign_month(ink_names, month, year, theme, theme_description)** - Assign multiple inks to a month at once
6. **get_current_assignments_summary(year)** - Get overview of all assignments

### Setup

1. Get an API key from either:
   - **Anthropic (Claude)**: https://console.anthropic.com/ (recommended, default)
   - **OpenAI (GPT-4)**: https://platform.openai.com/

2. Add to your `.env` file:
   ```bash
   ANTHROPIC_API_KEY=your_key_here
   # OR
   OPENAI_API_KEY=your_key_here
   ```

3. Go to the "🤖 LLM Organizer" tab in the app

4. Select your provider (Anthropic or OpenAI)

5. Click "🆕 Start New Chat"

6. Have a conversation! Examples:
   ```
   "Show me all my blue inks"
   "What's currently assigned to March?"
   "Assign Diamine Blue Velvet to February 14th with theme 'Valentine's Day'"
   "I want May to be all greens and blues - can you assign them for me?"
   "Fill December with festive reds and greens"
   ```

### How It Works

When you start a chat:
1. The AI receives information about your collection and the current year
2. You can ask questions and make requests naturally
3. The AI uses tools to search, view, and modify assignments
4. Changes happen in real-time - the calendar updates immediately
5. The conversation history is preserved for context

### Protection Rules

**IMPORTANT**: Inks that already have assignments in their `comment` field (via the manual JSON method) are **protected** and cannot be modified by the AI:

- The AI will see these inks marked as `already_assigned: true`
- Attempts to reassign them will be automatically rejected
- They're skipped in bulk operations
- Only you can manually change them via the FPC website

This ensures the AI never overwrites your carefully planned assignments!

### Example Conversation

```
You: What inks do I have available for February?

AI: [Uses search_inks() and get_month_assignments()]
You have 45 inks not yet assigned. Would you like me to suggest some for February?

You: Yes, make it romantic blues and purples for Valentine's month.

AI: [Uses assign_ink_to_date() multiple times]
I've assigned:
- Feb 1: Pilot Iroshizuku Kon-peki
- Feb 14: Diamine Oxblood (romantic deep red)
- Feb 28: Sailor Ink Studio 280 (purple)
... and 25 more. Would you like me to continue or adjust any of these?

You: Perfect! What about March?

AI: [Uses get_month_assignments(3)]
March currently has 12 days assigned. Would you like me to fill in the rest with spring greens?
```

## Testing

Run the test suite:

```bash
pytest test_assignment_logic.py test_api_client.py -v
```

All 33 tests should pass.

## Project Structure

```
ink_scheduler/
├── app.py                      # Main Shiny application
├── assignment_logic.py         # Core assignment algorithms (pure functions)
├── api_client.py              # API client with pagination support
├── test_assignment_logic.py   # Tests for assignment logic
├── test_api_client.py         # Tests for API client
├── .env                       # Your API token (git-ignored)
├── .env.example              # Template for .env file
└── README.md                 # This file
```

## API Integration

The app uses the [Fountain Pen Companion API](https://www.fountainpencompanion.com/api-docs/) to fetch your ink collection. It automatically handles:

- **Pagination** - Fetches all pages of your collection
- **Authentication** - Uses Bearer token from environment
- **Data Flattening** - Simplifies the nested API structure

## Development

The codebase is structured with testability in mind:

- **Pure Functions** - Core logic separated from UI
- **Type Hints** - Better code documentation
- **Comprehensive Tests** - High test coverage
- **Clean Architecture** - Separation of concerns

## License

This is a personal project for fountain pen enthusiasts.
