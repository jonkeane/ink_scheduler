"""
Tests for API client pagination
"""
import pytest
from unittest.mock import Mock, patch
from api_client import fetch_all_collected_inks, flatten_ink_data


def test_flatten_ink_data():
    """Test flattening of nested API response structure"""
    raw_ink = {
        "id": "123",
        "type": "collected_ink",
        "attributes": {
            "brand_name": "Pilot",
            "ink_name": "Iroshizuku Kon-peki",
            "color": "#3366cc",
            "kind": "bottled",
            "swabbed": True,
            "used": False,
            "archived": False,
            "private": False,
            "usage_count": 5,
        }
    }

    flattened = flatten_ink_data(raw_ink)

    assert flattened["id"] == "123"
    assert flattened["brand_name"] == "Pilot"
    assert flattened["name"] == "Iroshizuku Kon-peki"
    assert flattened["color"] == "#3366cc"
    assert flattened["kind"] == "bottled"
    assert flattened["swabbed"] is True
    assert flattened["used"] is False


def test_flatten_ink_data_missing_attributes():
    """Test flattening with missing attributes"""
    raw_ink = {
        "id": "456",
        "type": "collected_ink",
        "attributes": {}
    }

    flattened = flatten_ink_data(raw_ink)

    assert flattened["id"] == "456"
    assert flattened["brand_name"] == ""
    assert flattened["name"] == ""
    assert flattened["color"] == ""


@patch('api_client.requests.get')
def test_fetch_all_collected_inks_single_page(mock_get):
    """Test fetching when all inks fit on one page"""
    # Mock response
    mock_response = Mock()
    mock_response.json.return_value = {
        "data": [
            {
                "id": "1",
                "type": "collected_ink",
                "attributes": {
                    "brand_name": "Diamine",
                    "ink_name": "Oxford Blue",
                    "color": "#003366",
                    "kind": "bottled"
                }
            },
            {
                "id": "2",
                "type": "collected_ink",
                "attributes": {
                    "brand_name": "Noodler's",
                    "ink_name": "Black",
                    "color": "#000000",
                    "kind": "bottled"
                }
            }
        ],
        "meta": {
            "pagination": {
                "total_pages": 1,
                "current_page": 1,
                "next_page": None,
                "prev_page": None
            }
        }
    }
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    # Fetch inks
    inks = fetch_all_collected_inks("test_token")

    # Should have called API once
    assert mock_get.call_count == 1

    # Should have 2 inks
    assert len(inks) == 2
    assert inks[0]["name"] == "Oxford Blue"
    assert inks[1]["name"] == "Black"


@patch('api_client.requests.get')
def test_fetch_all_collected_inks_multiple_pages(mock_get):
    """Test fetching across multiple pages"""
    # Mock responses for 2 pages
    page1_response = Mock()
    page1_response.json.return_value = {
        "data": [
            {
                "id": "1",
                "type": "collected_ink",
                "attributes": {
                    "brand_name": "Pilot",
                    "ink_name": "Iroshizuku Tsuki-yo",
                    "color": "#1a5490"
                }
            }
        ],
        "meta": {
            "pagination": {
                "total_pages": 2,
                "current_page": 1,
                "next_page": 2,
                "prev_page": None
            }
        }
    }
    page1_response.raise_for_status = Mock()

    page2_response = Mock()
    page2_response.json.return_value = {
        "data": [
            {
                "id": "2",
                "type": "collected_ink",
                "attributes": {
                    "brand_name": "Sailor",
                    "ink_name": "Yama-dori",
                    "color": "#006f7b"
                }
            }
        ],
        "meta": {
            "pagination": {
                "total_pages": 2,
                "current_page": 2,
                "next_page": None,
                "prev_page": 1
            }
        }
    }
    page2_response.raise_for_status = Mock()

    mock_get.side_effect = [page1_response, page2_response]

    # Fetch inks
    inks = fetch_all_collected_inks("test_token")

    # Should have called API twice
    assert mock_get.call_count == 2

    # Should have 2 inks (1 from each page)
    assert len(inks) == 2
    assert inks[0]["name"] == "Iroshizuku Tsuki-yo"
    assert inks[1]["name"] == "Yama-dori"


@patch('api_client.requests.get')
def test_fetch_all_collected_inks_empty(mock_get):
    """Test fetching when user has no inks"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "data": [],
        "meta": {
            "pagination": {
                "total_pages": 0,
                "current_page": 1,
                "next_page": None,
                "prev_page": None
            }
        }
    }
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    inks = fetch_all_collected_inks("test_token")

    assert len(inks) == 0
    assert inks == []


@patch('api_client.requests.get')
def test_fetch_all_collected_inks_authentication_header(mock_get):
    """Test that authentication header is set correctly"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "data": [],
        "meta": {"pagination": {"total_pages": 0, "current_page": 1, "next_page": None}}
    }
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    fetch_all_collected_inks("my_secret_token")

    # Check that the Authorization header was set
    call_kwargs = mock_get.call_args[1]
    assert "headers" in call_kwargs
    assert call_kwargs["headers"]["Authorization"] == "Bearer my_secret_token"


@patch('api_client.requests.get')
def test_fetch_all_collected_inks_pagination_params(mock_get):
    """Test that pagination parameters are sent correctly"""
    mock_response = Mock()
    mock_response.json.return_value = {
        "data": [],
        "meta": {"pagination": {"total_pages": 0, "current_page": 1, "next_page": None}}
    }
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    fetch_all_collected_inks("token")

    # Check pagination params
    call_kwargs = mock_get.call_args[1]
    assert "params" in call_kwargs
    assert call_kwargs["params"]["page[number]"] == 1
    assert call_kwargs["params"]["page[size]"] == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
