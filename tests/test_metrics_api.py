"""Tests for get_edge_link_series API wrapper in vco_edge_export.

Verifies that the wrapper calls api_call with the correct JSON-RPC method
and parameter structure matching the VCO metrics/getEdgeLinkSeries contract
(METR-01).

Sets VCO_TOKEN and VCO_URL before importing vco_edge_export to avoid
loading real credentials from .env.
"""
import os
from unittest.mock import patch

os.environ["VCO_TOKEN"] = "Token test"
os.environ["VCO_URL"] = "https://test.example.com/portal/"

from vco_edge_export import get_edge_link_series  # noqa: E402


def test_get_edge_link_series_params():
    """get_edge_link_series passes correct method and params to api_call."""
    with patch("vco_edge_export.api_call") as mock_api_call:
        mock_api_call.return_value = {}
        get_edge_link_series(100, 200, 1000000, 2000000)

        mock_api_call.assert_called_once()
        call_args = mock_api_call.call_args
        assert call_args[0][0] == "metrics/getEdgeLinkSeries"
        assert call_args[0][1] == {
            "enterpriseId": 100,
            "edgeId": 200,
            "interval": {"start": 1000000, "end": 2000000},
            "metrics": ["bytesTx", "bytesRx"],
        }


def test_get_edge_link_series_returns_api_result():
    """get_edge_link_series returns whatever api_call returns."""
    with patch("vco_edge_export.api_call") as mock_api_call:
        mock_api_call.return_value = {"result": [{"series": []}]}
        result = get_edge_link_series(1, 2, 0, 1000)
        assert result == {"result": [{"series": []}]}
