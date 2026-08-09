"""Tests for output.py pure functions.

Covers: extract_vco_name, write_month_csvs, create_zip_archive.
No VCO credentials needed -- output.py is independent of VCO API.
"""
import os
import zipfile

import pandas as pd
import pytest

from output import create_zip_archive, extract_vco_name, write_month_csvs


# ── extract_vco_name ───────────────────────────────────────────────────────


class TestExtractVcoName:
    """Tests for VCO URL hostname extraction."""

    def test_standard_url(self):
        """extract_vco_name returns hostname from standard VCO URL with trailing slash."""
        assert extract_vco_name("https://vco.example.com/portal/") == "vco.example.com"

    def test_no_trailing_slash(self):
        """extract_vco_name returns hostname when path has no trailing slash."""
        assert extract_vco_name("https://vco.example.com/portal") == "vco.example.com"

    def test_subdomain_url(self):
        """extract_vco_name handles compound subdomains with hyphens."""
        assert (
            extract_vco_name("https://vco-prod.company.net/portal/")
            == "vco-prod.company.net"
        )

    def test_url_with_port(self):
        """extract_vco_name strips port number from hostname."""
        assert (
            extract_vco_name("https://vco.example.com:8443/portal/")
            == "vco.example.com"
        )

    def test_bare_url(self):
        """extract_vco_name returns hostname for URL with no path component."""
        assert extract_vco_name("https://vco.example.com") == "vco.example.com"

    def test_scheme_less_url_raises(self):
        """extract_vco_name raises ValueError for a URL without a scheme."""
        with pytest.raises(ValueError, match="scheme"):
            extract_vco_name("vco.example.com/portal/")

    def test_empty_url_raises(self):
        """extract_vco_name raises ValueError for an empty string."""
        with pytest.raises(ValueError, match="Cannot extract hostname"):
            extract_vco_name("")


# ── write_month_csvs ───────────────────────────────────────────────────────


class TestWriteMonthCsvs:
    """Tests for per-month CSV generation."""

    def _make_merged_df(self):
        """Build a minimal merged_df with 2 rows."""
        return pd.DataFrame(
            {
                "Customer Name": ["Acme Corp", "Beta Inc"],
                "Edge Name": ["edge-01", "edge-02"],
                "Edge UUID": ["uuid-aaa", "uuid-bbb"],
                "Edge Status": ["CONNECTED", "OFFLINE"],
            }
        )

    def _make_target_months_one(self):
        """Build a single target_months list for July 2026."""
        return [
            {
                "label": "07-2026",
                "year": 2026,
                "month": 7,
                "start_ms": 0,
                "end_ms": 0,
            }
        ]

    def _make_metrics_results_one(self):
        """Build metrics_results with one entry matching edge-01 for July 2026."""
        return [
            {
                "enterprise_name": "Acme Corp",
                "edge_name": "edge-01",
                "month_label": "07-2026",
                "monthly_tx_95th_mbps": 1.5,
                "monthly_rx_95th_mbps": 2.5,
                "monthly_total_95th_mbps": 4.0,
                "monthly_tx_max_mbps": 2.0,
                "monthly_rx_max_mbps": 3.0,
                "monthly_total_max_mbps": 5.0,
                "monthly_tx_avg_mbps": 1.0,
                "monthly_rx_avg_mbps": 1.8,
                "monthly_total_avg_mbps": 2.8,
            }
        ]

    def test_single_month_creates_one_csv(self, tmp_path):
        """write_month_csvs with 1 month returns a list of 1 path and creates the CSV file."""
        merged_df = self._make_merged_df()
        metrics_results = self._make_metrics_results_one()
        target_months = self._make_target_months_one()

        result = write_month_csvs(
            merged_df, metrics_results, target_months, "vco.test.com", str(tmp_path)
        )

        assert len(result) == 1
        assert (tmp_path / "vco.test.com.07-2026.csv").exists()

    def test_csv_has_additional_columns(self, tmp_path):
        """The written CSV contains all merged_df columns plus the 4 additional columns."""
        merged_df = self._make_merged_df()
        metrics_results = self._make_metrics_results_one()
        target_months = self._make_target_months_one()

        write_month_csvs(
            merged_df, metrics_results, target_months, "vco.test.com", str(tmp_path)
        )

        df = pd.read_csv(tmp_path / "vco.test.com.07-2026.csv")
        assert "Month-Year" in df.columns
        assert "monthly_tx_95th_mbps" in df.columns
        assert "monthly_rx_95th_mbps" in df.columns
        assert "monthly_total_95th_mbps" in df.columns
        assert "monthly_tx_max_mbps" in df.columns
        assert "monthly_rx_max_mbps" in df.columns
        assert "monthly_total_max_mbps" in df.columns
        assert "monthly_tx_avg_mbps" in df.columns
        assert "monthly_rx_avg_mbps" in df.columns
        assert "monthly_total_avg_mbps" in df.columns
        # Original merged_df columns must also be present
        for col in merged_df.columns:
            assert col in df.columns

    def test_month_year_column_set_for_all_rows(self, tmp_path):
        """Every row in the written CSV has Month-Year equal to the month label."""
        merged_df = self._make_merged_df()
        metrics_results = self._make_metrics_results_one()
        target_months = self._make_target_months_one()

        write_month_csvs(
            merged_df, metrics_results, target_months, "vco.test.com", str(tmp_path)
        )

        df = pd.read_csv(tmp_path / "vco.test.com.07-2026.csv")
        assert (df["Month-Year"] == "07-2026").all()

    def test_unmatched_edge_has_nan_metrics(self, tmp_path):
        """An edge with no metrics entry has NaN in all 3 p95 columns."""
        merged_df = self._make_merged_df()
        # Only edge-01 has metrics; edge-02 does not
        metrics_results = self._make_metrics_results_one()
        target_months = self._make_target_months_one()

        write_month_csvs(
            merged_df, metrics_results, target_months, "vco.test.com", str(tmp_path)
        )

        df = pd.read_csv(tmp_path / "vco.test.com.07-2026.csv")
        unmatched = df[df["Edge Name"] == "edge-02"]
        assert len(unmatched) == 1
        assert pd.isna(unmatched["monthly_tx_95th_mbps"].iloc[0])
        assert pd.isna(unmatched["monthly_rx_95th_mbps"].iloc[0])
        assert pd.isna(unmatched["monthly_total_95th_mbps"].iloc[0])
        assert pd.isna(unmatched["monthly_tx_max_mbps"].iloc[0])
        assert pd.isna(unmatched["monthly_rx_max_mbps"].iloc[0])
        assert pd.isna(unmatched["monthly_total_max_mbps"].iloc[0])
        assert pd.isna(unmatched["monthly_tx_avg_mbps"].iloc[0])
        assert pd.isna(unmatched["monthly_rx_avg_mbps"].iloc[0])
        assert pd.isna(unmatched["monthly_total_avg_mbps"].iloc[0])

    def test_two_months_creates_two_csvs(self, tmp_path):
        """write_month_csvs with 2 months returns a list of 2 paths and creates both files."""
        merged_df = self._make_merged_df()
        metrics_results = [
            {
                "enterprise_name": "Acme Corp",
                "edge_name": "edge-01",
                "month_label": "06-2026",
                "monthly_tx_95th_mbps": 0.5,
                "monthly_rx_95th_mbps": 0.8,
                "monthly_total_95th_mbps": 1.3,
                "monthly_tx_max_mbps": 0.7,
                "monthly_rx_max_mbps": 1.0,
                "monthly_total_max_mbps": 1.7,
                "monthly_tx_avg_mbps": 0.3,
                "monthly_rx_avg_mbps": 0.5,
                "monthly_total_avg_mbps": 0.8,
            },
            {
                "enterprise_name": "Acme Corp",
                "edge_name": "edge-01",
                "month_label": "07-2026",
                "monthly_tx_95th_mbps": 1.5,
                "monthly_rx_95th_mbps": 2.5,
                "monthly_total_95th_mbps": 4.0,
                "monthly_tx_max_mbps": 2.0,
                "monthly_rx_max_mbps": 3.0,
                "monthly_total_max_mbps": 5.0,
                "monthly_tx_avg_mbps": 1.0,
                "monthly_rx_avg_mbps": 1.8,
                "monthly_total_avg_mbps": 2.8,
            },
        ]
        target_months = [
            {
                "label": "06-2026",
                "year": 2026,
                "month": 6,
                "start_ms": 0,
                "end_ms": 0,
            },
            {
                "label": "07-2026",
                "year": 2026,
                "month": 7,
                "start_ms": 0,
                "end_ms": 0,
            },
        ]

        result = write_month_csvs(
            merged_df, metrics_results, target_months, "vco.test.com", str(tmp_path)
        )

        assert len(result) == 2
        assert (tmp_path / "vco.test.com.06-2026.csv").exists()
        assert (tmp_path / "vco.test.com.07-2026.csv").exists()


# ── create_zip_archive ─────────────────────────────────────────────────────


class TestCreateZipArchive:
    """Tests for zip archive packaging."""

    def _make_csv_dir(self, tmp_path):
        """Create a directory with 2 dummy CSV files."""
        csv_dir = tmp_path / "csvs"
        csv_dir.mkdir()
        (csv_dir / "vco.test.com.06-2026.csv").write_text("col1,col2\n1,2\n")
        (csv_dir / "vco.test.com.07-2026.csv").write_text("col1,col2\n3,4\n")
        return csv_dir

    def test_creates_zip_file(self, tmp_path):
        """create_zip_archive produces a zip file at the specified path."""
        csv_dir = self._make_csv_dir(tmp_path)
        zip_path = str(tmp_path / "output.zip")

        create_zip_archive(str(csv_dir), zip_path)

        assert (tmp_path / "output.zip").exists()

    def test_zip_contains_csv_filenames(self, tmp_path):
        """The zip archive contains the CSV filenames (not full absolute paths)."""
        csv_dir = self._make_csv_dir(tmp_path)
        zip_path = str(tmp_path / "output.zip")

        create_zip_archive(str(csv_dir), zip_path)

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
        assert "vco.test.com.06-2026.csv" in names
        assert "vco.test.com.07-2026.csv" in names

    def test_returns_zip_path(self, tmp_path):
        """create_zip_archive returns the zip file path as a string."""
        csv_dir = self._make_csv_dir(tmp_path)
        zip_path = str(tmp_path / "output.zip")

        result = create_zip_archive(str(csv_dir), zip_path)

        assert result == zip_path
