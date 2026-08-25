"""Tests for get_edge_link_series API wrapper in vco_edge_export.

Verifies that the wrapper calls api_call with the correct JSON-RPC method
and parameter structure matching the VCO metrics/getEdgeLinkSeries contract
(METR-01).

VCO_TOKEN and VCO_URL are set by conftest.py before this module is imported,
so vco_edge_export's module-level os.getenv() calls use test credentials.
"""
from unittest.mock import patch

from vco_edge_export import (
    get_edge_link_series,
    parse_version_tuple,
    vco_supports_peak_metrics,
)


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


def test_get_edge_link_series_with_peak_metrics():
    """include_peak_metrics=True adds 4 extra metrics to the request."""
    with patch("vco_edge_export.api_call") as mock_api_call:
        mock_api_call.return_value = {}
        get_edge_link_series(100, 200, 1000000, 2000000, 8928, include_peak_metrics=True)

        call_args = mock_api_call.call_args
        metrics = call_args[0][1]["metrics"]
        assert metrics == [
            "bytesTx", "bytesRx",
            "maxIntervalBpsTx", "maxIntervalBpsRx",
            "minIntervalBpsTx", "minIntervalBpsRx",
        ]


def test_get_edge_link_series_without_peak_metrics():
    """include_peak_metrics=False (default) sends only bytesTx/Rx."""
    with patch("vco_edge_export.api_call") as mock_api_call:
        mock_api_call.return_value = {}
        get_edge_link_series(100, 200, 1000000, 2000000, 8928)

        call_args = mock_api_call.call_args
        metrics = call_args[0][1]["metrics"]
        assert metrics == ["bytesTx", "bytesRx"]


# ── parse_version_tuple ──────────────────────────────────────────────────


class TestParseVersionTuple:
    """Tests for version string parsing."""

    def test_four_part_version(self):
        assert parse_version_tuple("6.4.2.5") == (6, 4, 2, 5)

    def test_three_part_version(self):
        assert parse_version_tuple("6.4.2") == (6, 4, 2)

    def test_two_part_version(self):
        assert parse_version_tuple("6.4") == (6, 4)

    def test_single_part(self):
        assert parse_version_tuple("6") == (6,)

    def test_invalid_raises(self):
        import pytest
        with pytest.raises(ValueError):
            parse_version_tuple("abc.def")


# ── vco_supports_peak_metrics ────────────────────────────────────────────


class TestVcoSupportsPeakMetrics:
    """Tests for VCO version check for peak metrics support."""

    def test_version_6_4_supported(self):
        assert vco_supports_peak_metrics("6.4.0.0") is True

    def test_version_6_4_2_5_supported(self):
        assert vco_supports_peak_metrics("6.4.2.5") is True

    def test_version_7_0_supported(self):
        assert vco_supports_peak_metrics("7.0.0.0") is True

    def test_version_6_1_not_supported(self):
        assert vco_supports_peak_metrics("6.1.3.5") is False

    def test_version_5_2_not_supported(self):
        assert vco_supports_peak_metrics("5.2.3.14") is False

    def test_invalid_version_returns_false(self):
        assert vco_supports_peak_metrics("invalid") is False

    def test_empty_string_returns_false(self):
        assert vco_supports_peak_metrics("") is False
