"""Tests for output.py pure functions.

Covers: extract_vco_name, write_month_csvs, create_zip_archive.
No VCO credentials needed -- output.py is independent of VCO API.
"""
import os
import zipfile

import pandas as pd
import pytest

from encoder import SENTINEL_HASH
from output import create_zip_archive, extract_vco_name, write_combined_csv, write_month_csvs


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
        """The written CSV contains all merged_df columns plus the renamed p95 columns."""
        merged_df = self._make_merged_df()
        metrics_results = self._make_metrics_results_one()
        target_months = self._make_target_months_one()

        write_month_csvs(
            merged_df, metrics_results, target_months, "vco.test.com", str(tmp_path)
        )

        df = pd.read_csv(tmp_path / "vco.test.com.07-2026.csv")
        assert "Month-Year" in df.columns
        assert "30 Days 95th" in df.columns
        assert "30 Days P95 Peak" in df.columns
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
        """An edge with no metrics entry has NaN in the p95 columns."""
        merged_df = self._make_merged_df()
        metrics_results = self._make_metrics_results_one()
        target_months = self._make_target_months_one()

        write_month_csvs(
            merged_df, metrics_results, target_months, "vco.test.com", str(tmp_path)
        )

        df = pd.read_csv(tmp_path / "vco.test.com.07-2026.csv")
        unmatched = df[df["Edge Name"] == "edge-02"]
        assert len(unmatched) == 1
        assert pd.isna(unmatched["30 Days 95th"].iloc[0])
        assert pd.isna(unmatched["30 Days P95 Peak"].iloc[0])

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
            },
            {
                "enterprise_name": "Acme Corp",
                "edge_name": "edge-01",
                "month_label": "07-2026",
                "monthly_tx_95th_mbps": 1.5,
                "monthly_rx_95th_mbps": 2.5,
                "monthly_total_95th_mbps": 4.0,
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


class TestWriteMonthCsvsWithPeak:
    """Tests for peak P95 column in CSV output."""

    def _make_merged_df(self):
        return pd.DataFrame(
            {
                "Customer Name": ["Acme Corp", "Beta Inc"],
                "Edge Name": ["edge-01", "edge-02"],
                "Edge UUID": ["uuid-aaa", "uuid-bbb"],
                "Edge Status": ["CONNECTED", "OFFLINE"],
            }
        )

    def _make_target_months_one(self):
        return [{"label": "07-2026", "year": 2026, "month": 7, "start_ms": 0, "end_ms": 0}]

    def test_peak_column_present_when_include_peak_false(self, tmp_path):
        """30 Days P95 Peak column appears even when include_peak=False (VCO < 6.4)."""
        merged_df = self._make_merged_df()
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
        write_month_csvs(
            merged_df, metrics_results, self._make_target_months_one(),
            "vco.test.com", str(tmp_path), include_peak=False,
        )
        df = pd.read_csv(tmp_path / "vco.test.com.07-2026.csv")
        assert "30 Days P95 Peak" in df.columns
        assert pd.isna(df["30 Days P95 Peak"].iloc[0])

    def test_peak_column_has_data_when_include_peak_true(self, tmp_path):
        """30 Days P95 Peak column has values when include_peak=True (VCO >= 6.4)."""
        merged_df = self._make_merged_df()
        metrics_results = [
            {
                "enterprise_name": "Acme Corp",
                "edge_name": "edge-01",
                "month_label": "07-2026",
                "monthly_tx_95th_mbps": 1.5,
                "monthly_rx_95th_mbps": 2.5,
                "monthly_total_95th_mbps": 4.0,
                "monthly_peak_95th_mbps": 25.0,
            }
        ]
        write_month_csvs(
            merged_df, metrics_results, self._make_target_months_one(),
            "vco.test.com", str(tmp_path), include_peak=True,
        )
        df = pd.read_csv(tmp_path / "vco.test.com.07-2026.csv")
        assert "30 Days P95 Peak" in df.columns
        matched = df[df["Edge Name"] == "edge-01"]
        assert matched["30 Days P95 Peak"].iloc[0] == 25.0

    def test_peak_column_nan_for_unmatched_edge(self, tmp_path):
        """Unmatched edge has NaN in 30 Days P95 Peak column."""
        merged_df = self._make_merged_df()
        metrics_results = [
            {
                "enterprise_name": "Acme Corp",
                "edge_name": "edge-01",
                "month_label": "07-2026",
                "monthly_tx_95th_mbps": 1.5,
                "monthly_rx_95th_mbps": 2.5,
                "monthly_total_95th_mbps": 4.0,
                "monthly_peak_95th_mbps": 25.0,
            }
        ]
        write_month_csvs(
            merged_df, metrics_results, self._make_target_months_one(),
            "vco.test.com", str(tmp_path), include_peak=True,
        )
        df = pd.read_csv(tmp_path / "vco.test.com.07-2026.csv")
        unmatched = df[df["Edge Name"] == "edge-02"]
        assert pd.isna(unmatched["30 Days P95 Peak"].iloc[0])


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


# ── write_combined_csv ─────────────────────────────────────────────────────


class TestWriteCombinedCsv:
    """Tests for combined single-CSV generation with Record Hash column."""

    def _make_merged_df(self):
        """Build a minimal merged_df with 2 rows."""
        return pd.DataFrame(
            {
                "Customer Name": ["Acme Corp", "Beta Inc"],
                "Edge Name": ["edge-01", "edge-02"],
                "Edge UUID": ["uuid-aaa-111", "uuid-bbb-222"],
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
        """Build metrics_results with entries for both edges for July 2026."""
        return [
            {
                "enterprise_name": "Acme Corp",
                "edge_name": "edge-01",
                "month_label": "07-2026",
                "monthly_tx_95th_mbps": 1.5,
                "monthly_rx_95th_mbps": 2.5,
                "monthly_total_95th_mbps": 4.0,
                "monthly_peak_95th_mbps": 10.0,
            },
            {
                "enterprise_name": "Beta Inc",
                "edge_name": "edge-02",
                "month_label": "07-2026",
                "monthly_tx_95th_mbps": 0.5,
                "monthly_rx_95th_mbps": 0.8,
                "monthly_total_95th_mbps": 1.3,
                "monthly_peak_95th_mbps": 5.0,
            },
        ]

    def test_produces_single_csv_file(self, tmp_path):
        """write_combined_csv creates exactly 1 file named {vco_name}.combined.csv."""
        merged_df = self._make_merged_df()
        metrics_results = self._make_metrics_results_one()
        target_months = self._make_target_months_one()

        result = write_combined_csv(
            merged_df, metrics_results, target_months, "vco.test.com", str(tmp_path)
        )

        assert (tmp_path / "vco.test.com.combined.csv").exists()
        assert result == str(tmp_path / "vco.test.com.combined.csv")

    def test_csv_has_record_hash_column(self, tmp_path):
        """The written CSV contains a 'Record Hash' column."""
        merged_df = self._make_merged_df()
        metrics_results = self._make_metrics_results_one()
        target_months = self._make_target_months_one()

        write_combined_csv(
            merged_df, metrics_results, target_months, "vco.test.com", str(tmp_path)
        )

        df = pd.read_csv(tmp_path / "vco.test.com.combined.csv")
        assert "Record Hash" in df.columns

    def test_csv_has_no_metric_columns(self, tmp_path):
        """The combined CSV does NOT have per-month metric display columns."""
        merged_df = self._make_merged_df()
        metrics_results = self._make_metrics_results_one()
        target_months = self._make_target_months_one()

        write_combined_csv(
            merged_df, metrics_results, target_months, "vco.test.com", str(tmp_path)
        )

        df = pd.read_csv(tmp_path / "vco.test.com.combined.csv")
        assert "Month-Year" not in df.columns
        assert "30 Days 95th" not in df.columns
        assert "30 Days P95 Peak" not in df.columns

    def test_csv_has_all_merged_columns(self, tmp_path):
        """Every column from merged_df is present in the combined CSV."""
        merged_df = self._make_merged_df()
        metrics_results = self._make_metrics_results_one()
        target_months = self._make_target_months_one()

        write_combined_csv(
            merged_df, metrics_results, target_months, "vco.test.com", str(tmp_path)
        )

        df = pd.read_csv(tmp_path / "vco.test.com.combined.csv")
        for col in merged_df.columns:
            assert col in df.columns

    def test_one_row_per_edge(self, tmp_path):
        """The combined CSV has exactly one row per edge (same count as merged_df)."""
        merged_df = self._make_merged_df()
        metrics_results = self._make_metrics_results_one()
        target_months = self._make_target_months_one()

        write_combined_csv(
            merged_df, metrics_results, target_months, "vco.test.com", str(tmp_path)
        )

        df = pd.read_csv(tmp_path / "vco.test.com.combined.csv")
        assert len(df) == len(merged_df)

    def test_record_hash_length(self, tmp_path):
        """Every Record Hash value in the combined CSV is exactly 344 characters."""
        merged_df = self._make_merged_df()
        metrics_results = self._make_metrics_results_one()
        target_months = self._make_target_months_one()

        write_combined_csv(
            merged_df, metrics_results, target_months, "vco.test.com", str(tmp_path)
        )

        df = pd.read_csv(tmp_path / "vco.test.com.combined.csv")
        assert (df["Record Hash"].str.len() == 344).all()

    def test_empty_uuid_gets_sentinel(self, tmp_path):
        """An edge with empty Edge UUID gets SENTINEL_HASH as its Record Hash."""
        merged_df = pd.DataFrame(
            {
                "Customer Name": ["Sentinel Corp"],
                "Edge Name": ["edge-sentinel"],
                "Edge UUID": [""],
                "Edge Status": ["CONNECTED"],
            }
        )
        target_months = self._make_target_months_one()

        write_combined_csv(
            merged_df, [], target_months, "vco.test.com", str(tmp_path)
        )

        df = pd.read_csv(tmp_path / "vco.test.com.combined.csv")
        assert df["Record Hash"].iloc[0] == SENTINEL_HASH

    def test_edge_with_no_metrics(self, tmp_path):
        """An edge with no metrics_results entry still produces a valid 344-char Record Hash."""
        merged_df = self._make_merged_df()
        target_months = self._make_target_months_one()

        write_combined_csv(
            merged_df, [], target_months, "vco.test.com", str(tmp_path)
        )

        df = pd.read_csv(tmp_path / "vco.test.com.combined.csv")
        assert (df["Record Hash"].str.len() == 344).all()
