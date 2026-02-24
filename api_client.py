"""
API client for Fountain Pen Companion with pagination support
"""
import requests
from typing import List, Dict, Optional


def fetch_all_collected_inks(api_token: str, base_url: str = "https://www.fountainpencompanion.com/api/v1/collected_inks") -> List[Dict]:
    """
    Fetch all collected inks from the API, handling pagination automatically.

    Args:
        api_token: Bearer token for authentication
        base_url: API endpoint URL

    Returns:
        List of all ink data dictionaries (flattened from API format)

    Raises:
        requests.HTTPError: If any API request fails
        ValueError: If API returns unexpected format
    """
    headers = {"Authorization": f"Bearer {api_token}"}
    all_inks = []
    current_page = 1
    page_size = 100  # Request 100 items per page for efficiency

    while True:
        # Make paginated request
        params = {
            "page[number]": current_page,
            "page[size]": page_size,
            "include": "macro_cluster"
        }

        response = requests.get(base_url, headers=headers, params=params)
        response.raise_for_status()

        response_data = response.json()

        # Extract ink data from this page
        raw_inks = response_data.get("data", [])

        # Flatten the nested structure
        for item in raw_inks:
            attrs = item.get("attributes", {})
            flattened = {
                "id": item.get("id"),
                "brand_name": attrs.get("brand_name", ""),
                "line_name": attrs.get("line_name", ""),
                "name": attrs.get("ink_name", ""),  # API uses 'ink_name', we map to 'name'
                "maker": attrs.get("maker", ""),
                "color": attrs.get("color", ""),
                "cluster_tags": attrs.get("cluster_tags", []),
                "kind": attrs.get("kind", ""),
                "swabbed": attrs.get("swabbed", False),
                "used": attrs.get("used", False),
                "archived": attrs.get("archived", False),
                "private": attrs.get("private", False),
                "usage_count": attrs.get("usage", 0),
                "daily_usage": attrs.get("daily_usage", 0),
                "last_used_on": attrs.get("last_used_on", ""),
                "comment": attrs.get("comment", ""),  # Public comment from API
                "private_comment": attrs.get("private_comment", ""),  # Private comment (where assignments go)
                "simplified_brand_name": attrs.get("simplified_brand_name", ""),
                "simplified_ink_name": attrs.get("simplified_ink_name", ""),
            }
            all_inks.append(flattened)

        # Check pagination metadata
        meta = response_data.get("meta", {})
        pagination = meta.get("pagination", {})

        total_pages = pagination.get("total_pages", 1)
        next_page = pagination.get("next_page")

        # If there's no next page, we're done
        if next_page is None or current_page >= total_pages:
            break

        current_page = next_page

    return all_inks


def flatten_ink_data(raw_ink: Dict) -> Dict:
    """
    Flatten a single ink item from API nested structure.

    Args:
        raw_ink: Raw ink object from API with 'id', 'type', 'attributes', etc.

    Returns:
        Flattened dictionary with all attributes at top level
    """
    attrs = raw_ink.get("attributes", {})
    return {
        "id": raw_ink.get("id"),
        "brand_name": attrs.get("brand_name", ""),
        "line_name": attrs.get("line_name", ""),
        "name": attrs.get("ink_name", ""),
        "maker": attrs.get("maker", ""),
        "color": attrs.get("color", ""),
        "kind": attrs.get("kind", ""),
        "swabbed": attrs.get("swabbed", False),
        "used": attrs.get("used", False),
        "archived": attrs.get("archived", False),
        "private": attrs.get("private", False),
        "usage_count": attrs.get("usage_count", 0),
        "comment": attrs.get("comment", ""),  # Public comment from API
        "private_comment": attrs.get("private_comment", ""),  # Private comment (where assignments go)
    }


def fetch_single_ink(
    api_token: str,
    ink_id: str,
    base_url: str = "https://www.fountainpencompanion.com/api/v1/collected_inks"
) -> Dict:
    """
    Fetch a single ink by ID from the API.

    Args:
        api_token: Bearer token for authentication
        ink_id: The ID of the ink to fetch
        base_url: API endpoint URL

    Returns:
        Ink data dictionary (flattened)

    Raises:
        requests.HTTPError: If the API request fails
    """
    url = f"{base_url}/{ink_id}"
    headers = {"Authorization": f"Bearer {api_token}"}

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    response_data = response.json()
    return flatten_ink_data(response_data.get("data", {}))


def update_ink_private_comment(
    api_token: str,
    ink_id: str,
    private_comment: str,
    base_url: str = "https://www.fountainpencompanion.com/api/v1/collected_inks"
) -> Dict:
    """
    Update the private_comment field for a specific ink.

    Args:
        api_token: Bearer token for authentication
        ink_id: The ID of the ink to update
        private_comment: The new private_comment value (JSON string)
        base_url: API endpoint URL

    Returns:
        Updated ink data dictionary (flattened)

    Raises:
        requests.HTTPError: If the API request fails
    """
    url = f"{base_url}/{ink_id}"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "data": {
            "id": str(ink_id),
            "type": "collected_ink",
            "attributes": {
                "private_comment": private_comment
            }
        }
    }

    response = requests.patch(url, headers=headers, json=payload)

    response.raise_for_status()

    response_data = response.json()
    return flatten_ink_data(response_data.get("data", {}))
