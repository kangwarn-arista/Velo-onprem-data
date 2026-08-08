"""Tests verifying vco_edge_export correctly wires output module functions.

These tests call the REAL functions through the vco_edge_export namespace
(not mocks), confirming that imports resolve and produce correct results.

VCO_TOKEN and VCO_URL are set by conftest.py before this module is imported,
so vco_edge_export's module-level os.getenv() calls use test credentials.
"""
import zipfile

import pandas as pd

import vco_edge_export


# ── import availability ────────────────────────────────────────────────────


def test_output_imports_present():
    """Output module functions are importable from the vco_edge_export namespace."""
    from vco_edge_export import create_zip_archive, extract_vco_name, write_month_csvs

    assert callable(extract_vco_name)
    assert callable(write_month_csvs)
    assert callable(create_zip_archive)


# ── real invocation through vco_edge_export namespace ─────────────────────


def test_extract_vco_name_returns_hostname_via_namespace():
    """extract_vco_name called through vco_edge_export returns hostname from vco_url."""
    result = vco_edge_export.extract_vco_name(vco_edge_export.vco_url)
    # conftest sets VCO_URL to "https://test.example.com/portal/"
    assert result == "test.example.com"


def test_write_month_csvs_produces_csv_via_namespace(tmp_path):
    """write_month_csvs called through vco_edge_export creates a CSV file with metrics columns."""
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

    csv_paths = vco_edge_export.write_month_csvs(
        merged_df, metrics_results, target_months, "vco.test.com", str(tmp_path)
    )

    assert len(csv_paths) == 1
    assert (tmp_path / "vco.test.com.07-2026.csv").exists()
    df = pd.read_csv(csv_paths[0])
    assert "monthly_tx_95th_mbps" in df.columns


def test_create_zip_archive_produces_zip_via_namespace(tmp_path):
    """create_zip_archive called through vco_edge_export creates a valid zip with .zip extension."""
    csv_dir = tmp_path / "csvs"
    csv_dir.mkdir()
    (csv_dir / "test.csv").write_text("a,b\n1,2\n")
    zip_path = str(tmp_path / "output.zip")

    result = vco_edge_export.create_zip_archive(str(csv_dir), zip_path)

    assert result == zip_path
    assert result.endswith(".zip")
    with zipfile.ZipFile(zip_path, "r") as zf:
        assert "test.csv" in zf.namelist()
