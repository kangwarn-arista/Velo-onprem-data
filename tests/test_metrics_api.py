"""Tests for get_edge_link_series API wrapper in vco_edge_export.

Verifies that the wrapper calls api_call with the correct JSON-RPC method
and parameter structure matching the VCO metrics/getEdgeLinkSeries contract
(METR-01).

VCO_TOKEN and VCO_URL are set by conftest.py before this module is imported,
so vco_edge_export's module-level os.getenv() calls use test credentials.
"""
from unittest.mock import patch

from vco_edge_export import get_edge_link_series


def test_get_edge_link_series_params():
    """get_edge_link_series passes correct method, params, and maxSamples to api_call."""
    with patch("vco_edge_export.api_call") as mock_api_call:
        mock_api_call.return_value = {}
        get_edge_link_series(100, 200, 1000000, 2000000, 8928)

        mock_api_call.assert_called_once()
        call_args = mock_api_call.call_args
        assert call_args[0][0] == "metrics/getEdgeLinkSeries"
        assert call_args[0][1] == {
            "enterpriseId": 100,
            "edgeId": 200,
            "interval": {"start": 1000000, "end": 2000000},
            "maxSamples": 8928,
            "metrics": ["bytesTx", "bytesRx"],
        }


def test_get_edge_link_series_returns_api_result():
    """get_edge_link_series returns whatever api_call returns."""
    with patch("vco_edge_export.api_call") as mock_api_call:
        mock_api_call.return_value = {"result": [{"series": []}]}
        result = get_edge_link_series(1, 2, 0, 1000, 8928)
        assert result == {"result": [{"series": []}]}
