"""Tests for HA serial parsing and overwrite from get_edges().

License CSV HA is not the HA serial. ha_serial_from_edge reads the top-level
haSerialNumber from an edge dict, and overwrite_ha_from_edges replaces the
merged export HA column using Customer Name + Edge Name keys.
"""
import pandas as pd

from vco_edge_export import ha_serial_from_edge, overwrite_ha_from_edges


# ── ha_serial_from_edge ──────────────────────────────────────────────────


class TestHaSerialFromEdge:
    """Tests for top-level haSerialNumber parsing."""

    def test_present_serial(self):
        assert ha_serial_from_edge({"haSerialNumber": "VC123"}) == "VC123"

    def test_strips_whitespace(self):
        assert ha_serial_from_edge({"haSerialNumber": "  VC123  "}) == "VC123"

    def test_json_null(self):
        assert ha_serial_from_edge({"haSerialNumber": None}) == ""

    def test_missing_key(self):
        assert ha_serial_from_edge({}) == ""

    def test_empty_string(self):
        assert ha_serial_from_edge({"haSerialNumber": ""}) == ""

    def test_whitespace_only(self):
        assert ha_serial_from_edge({"haSerialNumber": "   "}) == ""

    def test_nested_ha_ignored(self):
        assert ha_serial_from_edge({"ha": {"haSerialNumber": "VC999"}}) == ""

    def test_literal_string_null_kept(self):
        assert ha_serial_from_edge({"haSerialNumber": "null"}) == "null"


# ── overwrite_ha_from_edges ──────────────────────────────────────────────


class TestOverwriteHaFromEdges:
    """Tests for in-place HA overwrite keyed by Customer Name + Edge Name."""

    def test_matched_row_replaces_license_ha(self):
        merged = pd.DataFrame(
            {
                "Customer Name": ["Acme"],
                "HA": ["YES"],
                "Edge Name": ["edge-1"],
            }
        )
        edges = pd.DataFrame(
            {
                "Customer Name": ["Acme"],
                "Edge Name": ["edge-1"],
                "HA": ["VC123"],
            }
        )
        result = overwrite_ha_from_edges(merged, edges)
        assert result is merged
        assert result.loc[0, "HA"] == "VC123"
        assert "HA_x" not in result.columns
        assert "HA_y" not in result.columns

    def test_matched_row_blank_serial_blanks_ha(self):
        merged = pd.DataFrame(
            {
                "Customer Name": ["Acme"],
                "HA": ["YES"],
                "Edge Name": ["edge-1"],
            }
        )
        edges = pd.DataFrame(
            {
                "Customer Name": ["Acme"],
                "Edge Name": ["edge-1"],
                "HA": [""],
            }
        )
        result = overwrite_ha_from_edges(merged, edges)
        assert result.loc[0, "HA"] == ""

    def test_unmatched_license_row_blanks_ha(self):
        merged = pd.DataFrame(
            {
                "Customer Name": ["Acme"],
                "HA": ["YES"],
                "Edge Name": ["edge-1"],
            }
        )
        edges = pd.DataFrame(
            {
                "Customer Name": ["Other"],
                "Edge Name": ["edge-2"],
                "HA": ["VC123"],
            }
        )
        result = overwrite_ha_from_edges(merged, edges)
        assert result.loc[0, "HA"] == ""

    def test_column_order_preserved_when_ha_exists(self):
        merged = pd.DataFrame(
            {
                "Customer Name": ["Acme"],
                "HA": ["YES"],
                "Edge Name": ["edge-1"],
            }
        )
        edges = pd.DataFrame(
            {
                "Customer Name": ["Acme"],
                "Edge Name": ["edge-1"],
                "HA": ["VC123"],
            }
        )
        result = overwrite_ha_from_edges(merged, edges)
        assert list(result.columns) == ["Customer Name", "HA", "Edge Name"]

    def test_missing_ha_column_created_other_columns_unchanged(self):
        merged = pd.DataFrame(
            {
                "Customer Name": ["Acme"],
                "Edge Name": ["edge-1"],
                "Edge UUID": ["uuid-1"],
                "Edge Status": ["CONNECTED"],
            }
        )
        edges = pd.DataFrame(
            {
                "Customer Name": ["Acme"],
                "Edge Name": ["edge-1"],
                "HA": ["VC123"],
            }
        )
        result = overwrite_ha_from_edges(merged, edges)
        assert result.loc[0, "HA"] == "VC123"
        assert result.loc[0, "Edge UUID"] == "uuid-1"
        assert result.loc[0, "Edge Status"] == "CONNECTED"
        assert list(result.columns) == [
            "Customer Name",
            "Edge Name",
            "Edge UUID",
            "Edge Status",
            "HA",
        ]
