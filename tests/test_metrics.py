"""Tests for metrics.py pure computation functions.

Covers: get_target_months, bytes_to_mbps, percentile_95,
aggregate_link_samples, compute_edge_month_metrics.
No VCO credentials needed -- metrics.py uses only stdlib.
"""
from datetime import date, datetime, timezone

import pytest

from metrics import (
    aggregate_link_samples,
    bytes_to_mbps,
    compute_edge_month_metrics,
    get_target_months,
    percentile_95,
)


# ── get_target_months ──────────────────────────────────────────────────────


class TestGetTargetMonths:
    """Tests for month range generation."""

    def test_single_month_returns_previous(self):
        """get_target_months(1, date(2026, 8, 5)) returns July 2026."""
        result = get_target_months(1, date(2026, 8, 5))
        assert len(result) == 1
        assert result[0]["label"] == "07-2026"
        assert result[0]["year"] == 2026
        assert result[0]["month"] == 7

    def test_single_month_start_ms_is_utc_epoch_millis(self):
        """start_ms for July 2026 is 2026-07-01T00:00:00 UTC in milliseconds."""
        result = get_target_months(1, date(2026, 8, 5))
        # 2026-07-01T00:00:00 UTC = 1782864000 seconds
        expected_start_ms = 1782864000 * 1000
        assert result[0]["start_ms"] == expected_start_ms

    def test_single_month_end_ms_is_next_month_start(self):
        """end_ms for July 2026 is 2026-08-01T00:00:00 UTC in milliseconds."""
        result = get_target_months(1, date(2026, 8, 5))
        # 2026-08-01T00:00:00 UTC = 1785542400 seconds
        expected_end_ms = 1785542400 * 1000
        assert result[0]["end_ms"] == expected_end_ms

    def test_three_months_chronological_order(self):
        """get_target_months(3, date(2026, 8, 5)) returns May, Jun, Jul 2026."""
        result = get_target_months(3, date(2026, 8, 5))
        assert len(result) == 3
        labels = [m["label"] for m in result]
        assert labels == ["05-2026", "06-2026", "07-2026"]

    def test_year_boundary_crossing(self):
        """get_target_months(2, date(2026, 1, 15)) returns Nov 2025, Dec 2025."""
        result = get_target_months(2, date(2026, 1, 15))
        assert len(result) == 2
        assert result[0]["label"] == "11-2025"
        assert result[0]["year"] == 2025
        assert result[0]["month"] == 11
        assert result[1]["label"] == "12-2025"
        assert result[1]["year"] == 2025
        assert result[1]["month"] == 12

    def test_first_of_month_excludes_current(self):
        """get_target_months(1, date(2026, 8, 1)) returns July 2026."""
        result = get_target_months(1, date(2026, 8, 1))
        assert result[0]["label"] == "07-2026"

    def test_all_timestamps_are_13_digit_integers(self):
        """All start_ms and end_ms values are 13-digit integers."""
        result = get_target_months(3, date(2026, 8, 5))
        for month in result:
            assert isinstance(month["start_ms"], int)
            assert isinstance(month["end_ms"], int)
            assert len(str(month["start_ms"])) == 13
            assert len(str(month["end_ms"])) == 13

    def test_each_dict_has_year_and_month_keys(self):
        """Each result dict has year (int) and month (int) keys."""
        result = get_target_months(3, date(2026, 8, 5))
        for entry in result:
            assert "year" in entry
            assert "month" in entry
            assert isinstance(entry["year"], int)
            assert isinstance(entry["month"], int)


# ── bytes_to_mbps ──────────────────────────────────────────────────────────


class TestBytesToMbps:
    """Tests for bytes-to-Mbps conversion."""

    def test_zero_bytes(self):
        """bytes_to_mbps(0) returns 0.0."""
        assert bytes_to_mbps(0) == 0.0

    def test_one_megabyte_in_bytes(self):
        """bytes_to_mbps(1_048_576) returns exactly 8/300."""
        assert bytes_to_mbps(1_048_576) == pytest.approx(8 / 300)

    def test_exact_one_mbps(self):
        """bytes_to_mbps(39_321_600) returns exactly 1.0."""
        assert bytes_to_mbps(39_321_600) == 1.0


# ── percentile_95 ──────────────────────────────────────────────────────────


class TestPercentile95:
    """Tests for 95th percentile calculation."""

    def test_100_values(self):
        """percentile_95(range(1, 101)) returns 95."""
        assert percentile_95(list(range(1, 101))) == 95

    def test_288_values(self):
        """percentile_95(range(1, 289)) returns 274."""
        assert percentile_95(list(range(1, 289))) == 274

    def test_single_value(self):
        """percentile_95([42]) returns 42."""
        assert percentile_95([42]) == 42

    def test_two_values(self):
        """percentile_95([10, 20]) returns 20."""
        assert percentile_95([10, 20]) == 20

    def test_empty_list_raises(self):
        """percentile_95([]) raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            percentile_95([])


# ── aggregate_link_samples ─────────────────────────────────────────────────


class TestAggregateLinkSamples:
    """Tests for cross-link sample aggregation."""

    def test_single_link_single_sample(self):
        """Single link with one sample returns one aggregated entry."""
        links = [{"series": [{"bytesTx": 100, "bytesRx": 200}]}]
        result = aggregate_link_samples(links)
        assert result == [{"tx_bytes": 100, "rx_bytes": 200}]

    def test_two_links_sums_at_each_index(self):
        """Two links sum bytesTx and bytesRx at each sample index."""
        links = [
            {"series": [{"bytesTx": 100, "bytesRx": 200}]},
            {"series": [{"bytesTx": 50, "bytesRx": 60}]},
        ]
        result = aggregate_link_samples(links)
        assert result == [{"tx_bytes": 150, "rx_bytes": 260}]

    def test_empty_list(self):
        """Empty link list returns empty list."""
        assert aggregate_link_samples([]) == []

    def test_link_with_empty_series(self):
        """Link whose series is empty returns empty list."""
        assert aggregate_link_samples([{"series": []}]) == []

    def test_missing_bytes_keys_default_to_zero(self):
        """Missing bytesTx/bytesRx keys default to 0."""
        links = [{"series": [{"bytesTx": 100}]}]
        result = aggregate_link_samples(links)
        assert result == [{"tx_bytes": 100, "rx_bytes": 0}]

    def test_missing_series_key(self):
        """Link dict without 'series' key treated as empty series."""
        links = [{"other": "data"}]
        result = aggregate_link_samples(links)
        assert result == []

    def test_multiple_samples_multiple_links(self):
        """Two links with 2 samples each aggregate correctly."""
        links = [
            {"series": [{"bytesTx": 10, "bytesRx": 20}, {"bytesTx": 30, "bytesRx": 40}]},
            {"series": [{"bytesTx": 5, "bytesRx": 6}, {"bytesTx": 7, "bytesRx": 8}]},
        ]
        result = aggregate_link_samples(links)
        assert result == [
            {"tx_bytes": 15, "rx_bytes": 26},
            {"tx_bytes": 37, "rx_bytes": 48},
        ]


# ── compute_edge_month_metrics ─────────────────────────────────────────────


class TestComputeEdgeMonthMetrics:
    """Tests for the full edge-month metrics pipeline."""

    # 2026-07-01T00:00:00 UTC in milliseconds
    JULY_START_MS = int(datetime(2026, 7, 1, tzinfo=timezone.utc).timestamp() * 1000)

    def test_empty_link_series_returns_zeros(self):
        """Empty link_series_result returns all-zero metrics dict."""
        result = compute_edge_month_metrics([], 0)
        assert result == {
            "monthly_tx_95th_mbps": 0.0,
            "monthly_rx_95th_mbps": 0.0,
            "monthly_total_95th_mbps": 0.0,
            "monthly_tx_max_mbps": 0.0,
            "monthly_rx_max_mbps": 0.0,
            "monthly_total_max_mbps": 0.0,
            "monthly_tx_avg_mbps": 0.0,
            "monthly_rx_avg_mbps": 0.0,
            "monthly_total_avg_mbps": 0.0,
        }

    def test_uniform_data_288_samples(self):
        """288 identical samples (1 day) with known byte values."""
        # 288 samples = 1 full day of 5-minute intervals
        links = [
            {"series": [{"bytesTx": 1_048_576, "bytesRx": 2_097_152}] * 288}
        ]
        result = compute_edge_month_metrics(links, self.JULY_START_MS)
        # All samples identical -> p95/max/avg of identical values = that value
        assert result["monthly_tx_95th_mbps"] == pytest.approx(8 / 300)
        assert result["monthly_rx_95th_mbps"] == pytest.approx(16 / 300)
        assert result["monthly_total_95th_mbps"] == pytest.approx(24 / 300)
        assert result["monthly_tx_max_mbps"] == pytest.approx(8 / 300)
        assert result["monthly_rx_max_mbps"] == pytest.approx(16 / 300)
        assert result["monthly_total_max_mbps"] == pytest.approx(24 / 300)
        assert result["monthly_tx_avg_mbps"] == pytest.approx(8 / 300)
        assert result["monthly_rx_avg_mbps"] == pytest.approx(16 / 300)
        assert result["monthly_total_avg_mbps"] == pytest.approx(24 / 300)

    def test_total_is_from_raw_bytes_not_sum_of_converted(self):
        """total_mbps is bytes_to_mbps(tx_bytes + rx_bytes), not tx_mbps + rx_mbps."""
        # With single sample, result should be bytes_to_mbps(tx + rx)
        links = [{"series": [{"bytesTx": 1_048_576, "bytesRx": 2_097_152}]}]
        result = compute_edge_month_metrics(links, self.JULY_START_MS)
        # bytes_to_mbps(1_048_576 + 2_097_152) = bytes_to_mbps(3_145_728)
        expected_total = 3_145_728 * 8 / 1_048_576 / 300
        assert result["monthly_total_95th_mbps"] == pytest.approx(expected_total)

    def test_result_has_nine_keys(self):
        """Result dict has exactly the nine expected metric keys."""
        links = [{"series": [{"bytesTx": 100, "bytesRx": 200}]}]
        result = compute_edge_month_metrics(links, self.JULY_START_MS)
        assert set(result.keys()) == {
            "monthly_tx_95th_mbps",
            "monthly_rx_95th_mbps",
            "monthly_total_95th_mbps",
            "monthly_tx_max_mbps",
            "monthly_rx_max_mbps",
            "monthly_total_max_mbps",
            "monthly_tx_avg_mbps",
            "monthly_rx_avg_mbps",
            "monthly_total_avg_mbps",
        }

    def test_multi_day_grouping(self):
        """Samples spanning 2 days produce daily p95 values then monthly p95/max/avg."""
        # 576 samples = 2 full days
        # Day 1: 288 samples at 1_048_576 tx bytes -> tx_mbps = 8/300
        # Day 2: 288 samples at 2_097_152 tx bytes -> tx_mbps = 16/300
        day1 = [{"bytesTx": 1_048_576, "bytesRx": 0}] * 288
        day2 = [{"bytesTx": 2_097_152, "bytesRx": 0}] * 288
        links = [{"series": day1 + day2}]
        result = compute_edge_month_metrics(links, self.JULY_START_MS)
        # Day 1 p95 = 8/300 (all identical), Day 2 p95 = 16/300 (all identical)
        # Monthly p95 of [8/300, 16/300] -> ceil(2 * 0.95) = 2 -> second value = 16/300
        assert result["monthly_tx_95th_mbps"] == pytest.approx(16 / 300)
        # max of [8/300, 16/300] = 16/300
        assert result["monthly_tx_max_mbps"] == pytest.approx(16 / 300)
        # avg of [8/300, 16/300] = (8/300 + 16/300) / 2 = 12/300
        assert result["monthly_tx_avg_mbps"] == pytest.approx(12 / 300)
        # rx bytes are 0 -> all rx and total metrics reflect that
        assert result["monthly_rx_max_mbps"] == 0.0
        assert result["monthly_rx_avg_mbps"] == 0.0
        assert result["monthly_total_max_mbps"] == pytest.approx(16 / 300)
        assert result["monthly_total_avg_mbps"] == pytest.approx(12 / 300)
