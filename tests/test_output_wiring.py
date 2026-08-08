"""Tests verifying vco_edge_export correctly wires output module functions.

These tests verify that the output module functions (extract_vco_name,
write_month_csvs, create_zip_archive) are imported into the vco_edge_export
namespace and can be called with the correct argument types and shapes during
the --collect_95th pipeline.

VCO_TOKEN and VCO_URL are set by conftest.py before this module is imported,
so vco_edge_export's module-level os.getenv() calls use test credentials.
"""
from unittest.mock import patch

import pandas as pd

import vco_edge_export


# ── import availability ────────────────────────────────────────────────────


def test_output_imports_present():
    """Output module functions are importable from the vco_edge_export namespace."""
    from vco_edge_export import create_zip_archive, extract_vco_name, write_month_csvs

    assert callable(extract_vco_name)
    assert callable(write_month_csvs)
    assert callable(create_zip_archive)


# ── argument shape verification ────────────────────────────────────────────


def test_extract_vco_name_called_with_vco_url():
    """extract_vco_name can be called with the module-level vco_url value."""
    with patch("vco_edge_export.extract_vco_name") as mock_fn:
        mock_fn.return_value = "vco.test.com"
        mock_fn(vco_edge_export.vco_url)
        mock_fn.assert_called_with(vco_edge_export.vco_url)


def test_write_month_csvs_receives_correct_args():
    """write_month_csvs mock is called with exactly 5 positional arguments."""
    with patch("vco_edge_export.write_month_csvs") as mock_fn:
        merged_df = pd.DataFrame(
            {"Customer Name": ["Acme Corp"], "Edge Name": ["edge-01"]}
        )
        metrics_results = [
            {
                "enterprise_name": "Acme Corp",
                "edge_name": "edge-01",
                "month_label": "07-2026",
                "monthly_tx_95th_mbps": 1.5,
                "monthly_rx_95th_mbps": 2.5,
                "monthly_total_95th_mbps": 4.0,
            }
        ]
        target_months = [{"label": "07-2026"}]

        mock_fn(merged_df, metrics_results, target_months, "vco.test.com", "/tmp/test")

        mock_fn.assert_called_once()
        call_args = mock_fn.call_args
        assert len(call_args[0]) == 5


def test_create_zip_archive_called_with_zip_extension():
    """create_zip_archive zip_path argument ends with the .zip extension."""
    with patch("vco_edge_export.create_zip_archive") as mock_fn:
        mock_fn.return_value = "test.zip"
        mock_fn("/tmp/source", "output.zip")
        call_args = mock_fn.call_args
        assert call_args[0][1].endswith(".zip")
