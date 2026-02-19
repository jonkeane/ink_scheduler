"""
Shared pytest fixtures for ink scheduler tests.
"""
import pytest


class MockReactive:
    """Mock Shiny reactive value for testing."""

    def __init__(self, initial_value):
        self._value = initial_value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


@pytest.fixture
def mock_reactive():
    """Factory fixture for creating mock reactive values."""
    return MockReactive


@pytest.fixture
def sample_inks():
    """Standard set of sample inks for testing."""
    return [
        {
            "id": "1",
            "brand_name": "Diamine",
            "name": "Blue Velvet",
            "color": "#1a237e",
            "line_name": "Standard",
            "cluster_tags": ["blue", "dark"],
            "comment": "A beautiful deep blue",
            "kind": "fountain pen ink",
            "used": True,
            "private_comment": ""
        },
        {
            "id": "2",
            "brand_name": "Pilot",
            "name": "Iroshizuku Kon-peki",
            "color": "#3366cc",
            "line_name": "Iroshizuku",
            "cluster_tags": ["blue", "teal"],
            "comment": "Cerulean blue",
            "kind": "fountain pen ink",
            "used": False,
            "private_comment": '{"swatch2026": {"date": "2026-01-15"}}'
        },
        {
            "id": "3",
            "brand_name": "Noodler's",
            "name": "Apache Sunset",
            "color": "#ff6600",
            "line_name": "",
            "cluster_tags": ["orange", "red"],
            "comment": "Vibrant orange-red",
            "kind": "fountain pen ink",
            "used": True,
            "private_comment": ""
        },
        {
            "id": "4",
            "brand_name": "Sailor",
            "name": "Yama-dori",
            "color": "#006666",
            "line_name": "Jentle Four Seasons",
            "cluster_tags": ["teal", "green"],
            "comment": "Teal with red sheen",
            "kind": "fountain pen ink",
            "used": False,
            "private_comment": ""
        },
        {
            "id": "5",
            "brand_name": "Diamine",
            "name": "Oxblood",
            "color": "#660000",
            "line_name": "Standard",
            "cluster_tags": ["red", "dark"],
            "comment": "Deep burgundy red",
            "kind": "fountain pen ink",
            "used": True,
            "private_comment": ""
        }
    ]


@pytest.fixture
def sample_inks_minimal():
    """Minimal ink data with only required fields."""
    return [
        {
            "id": "1",
            "brand_name": "Test Brand",
            "name": "Test Ink"
        },
        {
            "id": "2",
            "brand_name": "Another Brand",
            "name": "Another Ink"
        }
    ]


@pytest.fixture
def mock_llm_response():
    """Sample LLM JSON response for monthly theme assignments."""
    return '''{
    "monthly_themes": {
        "1": {
            "month_name": "January",
            "theme": "Winter Blues",
            "theme_description": "Cool tones for cold days",
            "ink_indices": [0, 1]
        },
        "2": {
            "month_name": "February",
            "theme": "Valentine Reds",
            "theme_description": "Warm reds for the month of love",
            "ink_indices": [2, 4]
        },
        "3": {
            "month_name": "March",
            "theme": "Spring Greens",
            "theme_description": "Fresh greens for new beginnings",
            "ink_indices": [3]
        },
        "4": {
            "month_name": "April",
            "theme": "Rainy Blues",
            "theme_description": "Soft blues like spring rain",
            "ink_indices": []
        },
        "5": {
            "month_name": "May",
            "theme": "Flower Colors",
            "theme_description": "Bright colors like May flowers",
            "ink_indices": []
        },
        "6": {
            "month_name": "June",
            "theme": "Summer Brights",
            "theme_description": "Vibrant summer colors",
            "ink_indices": []
        },
        "7": {
            "month_name": "July",
            "theme": "Firework Colors",
            "theme_description": "Bold colors for celebrations",
            "ink_indices": []
        },
        "8": {
            "month_name": "August",
            "theme": "Late Summer",
            "theme_description": "Warm earth tones",
            "ink_indices": []
        },
        "9": {
            "month_name": "September",
            "theme": "Back to School",
            "theme_description": "Classic academic colors",
            "ink_indices": []
        },
        "10": {
            "month_name": "October",
            "theme": "Autumn Leaves",
            "theme_description": "Orange and red fall colors",
            "ink_indices": []
        },
        "11": {
            "month_name": "November",
            "theme": "Harvest Tones",
            "theme_description": "Rich harvest colors",
            "ink_indices": []
        },
        "12": {
            "month_name": "December",
            "theme": "Holiday Spirit",
            "theme_description": "Festive red and green",
            "ink_indices": []
        }
    },
    "reasoning": "Organized by seasonal color themes and holidays"
}'''


@pytest.fixture
def sample_session_assignments():
    """Sample session assignments dictionary."""
    return {
        "2026-01-01": 0,
        "2026-01-15": 1,
        "2026-02-14": 4
    }


@pytest.fixture
def sample_api_assignments():
    """Sample API assignments dictionary (protected, from ink cache)."""
    return {
        "2026-01-15": 1,
        "2026-03-01": 3
    }


@pytest.fixture
def sample_session_themes():
    """Sample session themes dictionary."""
    return {
        "2026-01": {
            "theme": "Winter Blues",
            "description": "Cool tones for cold days"
        },
        "2026-02": {
            "theme": "Valentine Reds",
            "description": ""
        }
    }
