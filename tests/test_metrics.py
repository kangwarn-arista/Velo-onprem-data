"""Tests for metrics.py pure computation functions.

Covers: get_target_months, max_samples_for_month, bytes_to_mbps,
percentile_95, aggregate_link_samples, validate_sample_count,
compute_edge_month_metrics, diagnose_edge_metrics.
No VCO credentials needed -- metrics.py uses only stdlib.
"""
from datetime import date, datetime, timezone

import pytest

# Byte count for one 5-min sample that converts to exactly 1.0 Mbps
# (1_048_576 * 300 / 8 = BYTES_PER_SAMPLE_1MBPS)
BYTES_PER_SAMPLE_1MBPS = 39_321_600

from metrics import (
    aggregate_link_samples,
    bytes_to_mbps,
    compute_daily_p95s,
    compute_edge_month_metrics,
    diagnose_edge_metrics,
    get_last_30_days,
    get_target_months,
    max_samples_for_month,
    percentile_95,
    validate_sample_count,
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


# ── max_samples_for_month ─────────────────────────────────────────────────


class TestMaxSamplesForMonth:
    """Tests for month-aware sample count calculation."""

    def test_31_day_month(self):
        """July 2026 (31 days) returns 8928."""
        assert max_samples_for_month(2026, 7) == 8928

    def test_30_day_month(self):
        """June 2026 (30 days) returns 8640."""
        assert max_samples_for_month(2026, 6) == 8640

    def test_february_non_leap(self):
        """February 2025 (non-leap, 28 days) returns 8064."""
        assert max_samples_for_month(2025, 2) == 8064

    def test_february_leap_year(self):
        """February 2024 (leap year, 29 days) returns 8352."""
        assert max_samples_for_month(2024, 2) == 8352

    def test_max_possible_value(self):
        """No month exceeds 8928 samples (31 days × 288)."""
        for month in range(1, 13):
            assert max_samples_for_month(2026, month) <= 8928

    def test_january(self):
        """January (31 days) returns 8928."""
        assert max_samples_for_month(2026, 1) == 8928

    def test_april(self):
        """April (30 days) returns 8640."""
        assert max_samples_for_month(2026, 4) == 8640


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
        """bytes_to_mbps(BYTES_PER_SAMPLE_1MBPS) returns exactly 1.0."""
        assert bytes_to_mbps(BYTES_PER_SAMPLE_1MBPS) == 1.0


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
    """Tests for cross-link sample aggregation.

    The VCO API returns each link's series as metric objects:
    [{"metric": "bytesTx", "data": [v0, v1, ...]}, {"metric": "bytesRx", "data": [...]}]
    """

    def test_single_link_single_sample(self):
        """Single link with one sample returns one aggregated entry."""
        links = [{"series": [
            {"metric": "bytesTx", "data": [100]},
            {"metric": "bytesRx", "data": [200]},
        ]}]
        result = aggregate_link_samples(links)
        assert result == [{"tx_bytes": 100, "rx_bytes": 200}]

    def test_two_links_sums_at_each_index(self):
        """Two links sum bytesTx and bytesRx at each sample index."""
        links = [
            {"series": [
                {"metric": "bytesTx", "data": [100]},
                {"metric": "bytesRx", "data": [200]},
            ]},
            {"series": [
                {"metric": "bytesTx", "data": [50]},
                {"metric": "bytesRx", "data": [60]},
            ]},
        ]
        result = aggregate_link_samples(links)
        assert result == [{"tx_bytes": 150, "rx_bytes": 260}]

    def test_empty_list(self):
        """Empty link list returns empty list."""
        assert aggregate_link_samples([]) == []

    def test_link_with_empty_series(self):
        """Link whose series is empty returns empty list."""
        assert aggregate_link_samples([{"series": []}]) == []

    def test_missing_bytesRx_metric_defaults_to_zero(self):
        """Link with only bytesTx metric has rx default to 0."""
        links = [{"series": [
            {"metric": "bytesTx", "data": [100]},
        ]}]
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
            {"series": [
                {"metric": "bytesTx", "data": [10, 30]},
                {"metric": "bytesRx", "data": [20, 40]},
            ]},
            {"series": [
                {"metric": "bytesTx", "data": [5, 7]},
                {"metric": "bytesRx", "data": [6, 8]},
            ]},
        ]
        result = aggregate_link_samples(links)
        assert result == [
            {"tx_bytes": 15, "rx_bytes": 26},
            {"tx_bytes": 37, "rx_bytes": 48},
        ]

    def test_none_values_in_data_treated_as_zero(self):
        """None values in data arrays are treated as 0, not causing TypeError."""
        links = [{"series": [
            {"metric": "bytesTx", "data": [100, None, 200]},
            {"metric": "bytesRx", "data": [None, 300, None]},
        ]}]
        result = aggregate_link_samples(links)
        assert result == [
            {"tx_bytes": 100, "rx_bytes": 0},
            {"tx_bytes": 0, "rx_bytes": 300},
            {"tx_bytes": 200, "rx_bytes": 0},
        ]

    def test_all_none_data_produces_zeros(self):
        """An array of all None values produces zero-byte samples."""
        links = [{"series": [
            {"metric": "bytesTx", "data": [None, None]},
            {"metric": "bytesRx", "data": [None, None]},
        ]}]
        result = aggregate_link_samples(links)
        assert result == [
            {"tx_bytes": 0, "rx_bytes": 0},
            {"tx_bytes": 0, "rx_bytes": 0},
        ]


# ── validate_sample_count ─────────────────────────────────────────────────


class TestValidateSampleCount:
    """Tests for sample count validation."""

    def test_exact_match_valid(self):
        """Data length exactly matching expected is valid."""
        links = [{"linkId": 1, "series": [
            {"metric": "bytesTx", "data": [0] * 8928},
            {"metric": "bytesRx", "data": [0] * 8928},
        ]}]
        result = validate_sample_count(links, 8928)
        assert result["valid"] is True
        assert result["expected"] == 8928
        assert all(d["ok"] for d in result["links"])

    def test_plus_one_tolerance(self):
        """Data length of expected+1 is tolerated."""
        links = [{"linkId": 1, "series": [
            {"metric": "bytesTx", "data": [0] * 8929},
            {"metric": "bytesRx", "data": [0] * 8928},
        ]}]
        result = validate_sample_count(links, 8928)
        assert result["valid"] is True

    def test_minus_one_tolerance(self):
        """Data length of expected-1 is tolerated."""
        links = [{"linkId": 1, "series": [
            {"metric": "bytesTx", "data": [0] * 8927},
            {"metric": "bytesRx", "data": [0] * 8928},
        ]}]
        result = validate_sample_count(links, 8928)
        assert result["valid"] is True

    def test_beyond_tolerance_invalid(self):
        """Data length off by more than 1 is invalid."""
        links = [{"linkId": 1, "series": [
            {"metric": "bytesTx", "data": [0] * 8900},
            {"metric": "bytesRx", "data": [0] * 8928},
        ]}]
        result = validate_sample_count(links, 8928)
        assert result["valid"] is False
        tx_detail = next(d for d in result["links"] if d["metric"] == "bytesTx")
        assert tx_detail["ok"] is False
        assert tx_detail["actual"] == 8900
        assert tx_detail["diff"] == -28

    def test_strict_raises_on_failure(self):
        """strict=True raises ValueError when validation fails."""
        links = [{"linkId": 42, "series": [
            {"metric": "bytesTx", "data": [0] * 100},
        ]}]
        with pytest.raises(ValueError, match="link 42"):
            validate_sample_count(links, 8928, strict=True)

    def test_strict_no_raise_on_success(self):
        """strict=True does not raise when validation passes."""
        links = [{"linkId": 1, "series": [
            {"metric": "bytesTx", "data": [0] * 8928},
        ]}]
        result = validate_sample_count(links, 8928, strict=True)
        assert result["valid"] is True

    def test_multi_link(self):
        """Multiple links each contribute detail entries."""
        links = [
            {"linkId": 10, "series": [
                {"metric": "bytesTx", "data": [0] * 8928},
                {"metric": "bytesRx", "data": [0] * 8928},
            ]},
            {"linkId": 20, "series": [
                {"metric": "bytesTx", "data": [0] * 8928},
                {"metric": "bytesRx", "data": [0] * 8928},
            ]},
        ]
        result = validate_sample_count(links, 8928)
        assert result["valid"] is True
        assert len(result["links"]) == 4

    def test_empty_link_list(self):
        """Empty link list is considered valid (nothing to fail)."""
        result = validate_sample_count([], 8928)
        assert result["valid"] is True
        assert result["links"] == []

    def test_link_without_series(self):
        """Link missing 'series' key produces no detail entries."""
        result = validate_sample_count([{"linkId": 1}], 8928)
        assert result["valid"] is True
        assert result["links"] == []


# ── compute_daily_p95s ────────────────────────────────────────────────────


class TestComputeDailyP95s:
    """Tests for per-day P95 computation."""

    JULY_START_MS = int(datetime(2026, 7, 1, tzinfo=timezone.utc).timestamp() * 1000)

    def test_empty_link_series_returns_empty(self):
        """Empty link_series_result returns empty list."""
        assert compute_daily_p95s([], 0) == []

    def test_single_day_288_samples(self):
        """288 identical samples (1 full day) produce one daily entry."""
        links = [{"series": [
            {"metric": "bytesTx", "data": [1_048_576] * 288},
            {"metric": "bytesRx", "data": [2_097_152] * 288},
        ]}]
        result = compute_daily_p95s(links, self.JULY_START_MS)
        assert len(result) == 1
        assert result[0]["date"] == date(2026, 7, 1)
        assert result[0]["sample_count"] == 288
        assert result[0]["tx_p95"] == pytest.approx(8 / 300)
        assert result[0]["rx_p95"] == pytest.approx(16 / 300)
        assert result[0]["total_p95"] == pytest.approx(24 / 300)

    def test_daily_p95_picks_correct_rank(self):
        """288 ramping samples select the 274th-largest value (ceil(288 * 0.95))."""
        # Samples 1..288 as raw byte counts; P95 position = ceil(288*0.95) = 274
        tx_data = [i * BYTES_PER_SAMPLE_1MBPS for i in range(1, 289)]  # i Mbps each
        rx_data = [i * BYTES_PER_SAMPLE_1MBPS for i in range(1, 289)]
        links = [{"series": [
            {"metric": "bytesTx", "data": tx_data},
            {"metric": "bytesRx", "data": rx_data},
        ]}]
        result = compute_daily_p95s(links, self.JULY_START_MS)
        assert len(result) == 1
        # sorted values are 1..288 Mbps; position 274 (1-indexed) = 274 Mbps
        assert result[0]["tx_p95"] == pytest.approx(274.0)
        assert result[0]["rx_p95"] == pytest.approx(274.0)
        # total = bytes_to_mbps(tx_bytes + rx_bytes) = 2 * i Mbps; P95 = 2 * 274
        assert result[0]["total_p95"] == pytest.approx(548.0)

    def test_two_days_sorted_by_date(self):
        """576 samples spanning 2 days produce two entries in date order."""
        links = [{"series": [
            {"metric": "bytesTx", "data": [1_048_576] * 288 + [2_097_152] * 288},
            {"metric": "bytesRx", "data": [0] * 576},
        ]}]
        result = compute_daily_p95s(links, self.JULY_START_MS)
        assert len(result) == 2
        assert result[0]["date"] == date(2026, 7, 1)
        assert result[1]["date"] == date(2026, 7, 2)
        assert result[0]["tx_p95"] == pytest.approx(8 / 300)
        assert result[1]["tx_p95"] == pytest.approx(16 / 300)

    def test_result_keys(self):
        """Each daily entry has the expected keys."""
        links = [{"series": [
            {"metric": "bytesTx", "data": [100]},
            {"metric": "bytesRx", "data": [200]},
        ]}]
        result = compute_daily_p95s(links, self.JULY_START_MS)
        assert len(result) == 1
        assert set(result[0].keys()) == {
            "date", "sample_count", "tx_p95", "rx_p95", "total_p95",
        }

    def test_consistent_with_monthly_pipeline(self):
        """Daily P95s fed into monthly calc match compute_edge_month_metrics."""
        links = [{"series": [
            {"metric": "bytesTx", "data": [10 * BYTES_PER_SAMPLE_1MBPS] * 288 + [20 * BYTES_PER_SAMPLE_1MBPS] * 288},
            {"metric": "bytesRx", "data": [5 * BYTES_PER_SAMPLE_1MBPS] * 576},
        ]}]
        daily = compute_daily_p95s(links, self.JULY_START_MS)
        monthly = compute_edge_month_metrics(links, self.JULY_START_MS)

        all_tx = [d["tx_p95"] for d in daily]
        assert monthly["monthly_tx_95th_mbps"] == round(percentile_95(all_tx))
        assert monthly["monthly_tx_max_mbps"] == round(max(all_tx))
        assert monthly["monthly_tx_avg_mbps"] == round(
            sum(all_tx) / len(all_tx)
        )


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
        links = [{"series": [
            {"metric": "bytesTx", "data": [10 * BYTES_PER_SAMPLE_1MBPS] * 288},
            {"metric": "bytesRx", "data": [20 * BYTES_PER_SAMPLE_1MBPS] * 288},
        ]}]
        result = compute_edge_month_metrics(links, self.JULY_START_MS)
        # All samples identical -> p95/max/avg all equal the per-sample value
        assert result["monthly_tx_95th_mbps"] == 10
        assert result["monthly_rx_95th_mbps"] == 20
        assert result["monthly_total_95th_mbps"] == 30
        assert result["monthly_tx_max_mbps"] == 10
        assert result["monthly_rx_max_mbps"] == 20
        assert result["monthly_total_max_mbps"] == 30
        assert result["monthly_tx_avg_mbps"] == 10
        assert result["monthly_rx_avg_mbps"] == 20
        assert result["monthly_total_avg_mbps"] == 30

    def test_total_is_from_raw_bytes_not_sum_of_converted(self):
        """total_mbps is bytes_to_mbps(tx_bytes + rx_bytes), not tx_mbps + rx_mbps."""
        links = [{"series": [
            {"metric": "bytesTx", "data": [10 * BYTES_PER_SAMPLE_1MBPS]},
            {"metric": "bytesRx", "data": [20 * BYTES_PER_SAMPLE_1MBPS]},
        ]}]
        result = compute_edge_month_metrics(links, self.JULY_START_MS)
        expected_total = round(bytes_to_mbps(30 * BYTES_PER_SAMPLE_1MBPS))
        assert result["monthly_total_95th_mbps"] == expected_total

    def test_result_has_nine_keys(self):
        """Result dict has exactly the nine expected metric keys."""
        links = [{"series": [
            {"metric": "bytesTx", "data": [100]},
            {"metric": "bytesRx", "data": [200]},
        ]}]
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
        # Day 1: 288 samples at 10 Mbps tx, Day 2: 288 samples at 20 Mbps tx
        links = [{"series": [
            {"metric": "bytesTx", "data": [10 * BYTES_PER_SAMPLE_1MBPS] * 288 + [20 * BYTES_PER_SAMPLE_1MBPS] * 288},
            {"metric": "bytesRx", "data": [0] * 576},
        ]}]
        result = compute_edge_month_metrics(links, self.JULY_START_MS)
        # Day 1 p95 = 10, Day 2 p95 = 20
        # Monthly p95 of [10, 20] -> ceil(2 * 0.95) = 2 -> second value = 20
        assert result["monthly_tx_95th_mbps"] == 20
        # max of [10, 20] = 20
        assert result["monthly_tx_max_mbps"] == 20
        # avg of [10, 20] = 15
        assert result["monthly_tx_avg_mbps"] == 15
        # rx bytes are 0 -> all rx and total metrics reflect that
        assert result["monthly_rx_max_mbps"] == 0
        assert result["monthly_rx_avg_mbps"] == 0
        assert result["monthly_total_max_mbps"] == 20
        assert result["monthly_total_avg_mbps"] == 15

    def test_three_link_full_month_with_sample_validation(self):
        """3 links over a full July (31 days, 8928 samples) validates count and p95.

        Mirrors a real VCO response with realistic traffic scaled to produce
        integer Mbps values (×1000 from original MB/sample figures).
        """
        expected = max_samples_for_month(2026, 7)
        assert expected == 8928

        S = 1000  # scale factor for meaningful integer Mbps
        n = 288   # samples per day
        days = 31

        # Link 1: steady traffic, slight daily ramp
        link1_rx = []
        link1_tx = []
        for d in range(days):
            link1_rx.extend([S * 3_800_000 + d * S * 5_000] * n)
            link1_tx.extend([S * 2_300_000 + d * S * 3_000] * n)

        # Link 2: backup, all zeros except a burst on day 15
        link2_rx = [0] * expected
        link2_tx = [0] * expected
        burst_idx = 15 * n + 144  # midday on day 15
        link2_rx[burst_idx] = S * 8_000_000
        link2_tx[burst_idx] = S * 22_000_000

        # Link 3: steady traffic, slight daily ramp
        link3_rx = []
        link3_tx = []
        for d in range(days):
            link3_rx.extend([S * 2_000_000 + d * S * 2_000] * n)
            link3_tx.extend([S * 3_300_000 + d * S * 4_000] * n)

        links = [
            {"linkId": 532, "series": [
                {"metric": "bytesRx", "startTime": self.JULY_START_MS, "tickInterval": 300000, "data": link1_rx},
                {"metric": "bytesTx", "startTime": self.JULY_START_MS, "tickInterval": 300000, "data": link1_tx},
            ]},
            {"linkId": 533, "series": [
                {"metric": "bytesRx", "startTime": self.JULY_START_MS, "tickInterval": 300000, "data": link2_rx},
                {"metric": "bytesTx", "startTime": self.JULY_START_MS, "tickInterval": 300000, "data": link2_tx},
            ]},
            {"linkId": 534, "series": [
                {"metric": "bytesRx", "startTime": self.JULY_START_MS, "tickInterval": 300000, "data": link3_rx},
                {"metric": "bytesTx", "startTime": self.JULY_START_MS, "tickInterval": 300000, "data": link3_tx},
            ]},
        ]

        # Validate sample counts match expected maxSamples
        validation = validate_sample_count(links, expected)
        assert validation["valid"] is True
        assert validation["expected"] == 8928
        assert len(validation["links"]) == 6  # 3 links × 2 metrics each
        for detail in validation["links"]:
            assert detail["ok"] is True
            assert detail["actual"] == 8928

        # strict mode should also pass
        validate_sample_count(links, expected, strict=True)

        # Compute metrics
        result = compute_edge_month_metrics(links, self.JULY_START_MS)

        assert result["monthly_tx_95th_mbps"] > 0
        assert result["monthly_rx_95th_mbps"] > 0
        assert result["monthly_total_95th_mbps"] > 0

        # Day 30 (index 30, last day) has the highest steady traffic
        day30_rx = S * (3_950_000 + 2_060_000)
        day30_rx_mbps = bytes_to_mbps(day30_rx)

        day30_tx = S * (2_390_000 + 3_420_000)
        day30_tx_mbps = bytes_to_mbps(day30_tx)

        # Monthly p95 of 31 daily p95s: ceil(31 * 0.95) = 30 → 30th sorted value
        # Days are ramping up, so sorted daily p95s = day0..day30
        # 30th value (1-indexed) = day 29 (0-indexed)
        day29_rx = S * ((3_800_000 + 29 * 5_000) + (2_000_000 + 29 * 2_000))
        day29_tx = S * ((2_300_000 + 29 * 3_000) + (3_300_000 + 29 * 4_000))
        assert result["monthly_rx_95th_mbps"] == round(bytes_to_mbps(day29_rx))
        assert result["monthly_tx_95th_mbps"] == round(bytes_to_mbps(day29_tx))

        # Max should be day 30 (highest ramp)
        assert result["monthly_rx_max_mbps"] == round(day30_rx_mbps)
        assert result["monthly_tx_max_mbps"] == round(day30_tx_mbps)


# ── diagnose_edge_metrics ─────────────────────────────────────────────────


class TestDiagnoseEdgeMetrics:
    """Tests for the diagnostic analysis function."""

    def test_diagnose_healthy_data(self):
        """Returns expected structure for normal data with non-zero traffic."""
        links = [{"linkId": 10, "series": [
            {"metric": "bytesTx", "data": [100, 200]},
            {"metric": "bytesRx", "data": [300, 400]},
        ]}]
        result = diagnose_edge_metrics(links)
        assert result["link_count"] == 1
        assert len(result["links"]) == 1
        assert result["links"][0]["link_id"] == 10
        assert len(result["links"][0]["metrics"]) == 2
        tx_metric = result["links"][0]["metrics"][0]
        assert tx_metric["name"] == "bytesTx"
        assert tx_metric["samples"] == 2
        assert tx_metric["none_count"] == 0
        assert tx_metric["zero_count"] == 0
        assert result["total_samples_after_aggregation"] == 2
        assert result["all_zero"] is False

    def test_diagnose_with_none_values(self):
        """Correctly reports None counts in data arrays."""
        links = [{"linkId": 5, "series": [
            {"metric": "bytesTx", "data": [100, None, None]},
            {"metric": "bytesRx", "data": [None, 200, None]},
        ]}]
        result = diagnose_edge_metrics(links)
        tx_metric = result["links"][0]["metrics"][0]
        rx_metric = result["links"][0]["metrics"][1]
        assert tx_metric["none_count"] == 2
        assert rx_metric["none_count"] == 2
        assert result["total_samples_after_aggregation"] == 3
        assert result["all_zero"] is False

    def test_diagnose_empty_series(self):
        """Handles empty input gracefully."""
        result = diagnose_edge_metrics([])
        assert result["link_count"] == 0
        assert result["links"] == []
        assert result["total_samples_after_aggregation"] == 0
        assert result["all_zero"] is True

    def test_diagnose_all_zero_data(self):
        """Reports all_zero=True when every sample is zero."""
        links = [{"linkId": 1, "series": [
            {"metric": "bytesTx", "data": [0, 0]},
            {"metric": "bytesRx", "data": [0, 0]},
        ]}]
        result = diagnose_edge_metrics(links)
        assert result["all_zero"] is True
        assert result["links"][0]["metrics"][0]["zero_count"] == 2


# ── get_last_30_days ──────────────────────────────────────────────────────


class TestGetLast30Days:
    """Tests for the trailing-30-day time window."""

    def test_returns_single_element_list(self):
        result = get_last_30_days(reference_date=date(2026, 8, 8))
        assert isinstance(result, list)
        assert len(result) == 1

    def test_label_is_last30d(self):
        result = get_last_30_days(reference_date=date(2026, 8, 8))
        assert result[0]["label"] == "last30d"

    def test_has_all_expected_keys(self):
        result = get_last_30_days(reference_date=date(2026, 8, 8))
        entry = result[0]
        assert "year" in entry
        assert "month" in entry
        assert "start_ms" in entry
        assert "end_ms" in entry
        assert "label" in entry

    def test_window_spans_30_days(self):
        ref = date(2026, 8, 8)
        result = get_last_30_days(reference_date=ref)
        entry = result[0]
        duration_ms = entry["end_ms"] - entry["start_ms"]
        assert duration_ms == 30 * 24 * 60 * 60 * 1000

    def test_end_is_midnight_after_reference(self):
        ref = date(2026, 8, 8)
        result = get_last_30_days(reference_date=ref)
        entry = result[0]
        expected_end = datetime(2026, 8, 9, tzinfo=timezone.utc)
        assert entry["end_ms"] == int(expected_end.timestamp() * 1000)

    def test_start_is_30_days_before_end(self):
        ref = date(2026, 8, 8)
        result = get_last_30_days(reference_date=ref)
        entry = result[0]
        expected_start = datetime(2026, 7, 10, tzinfo=timezone.utc)
        assert entry["start_ms"] == int(expected_start.timestamp() * 1000)

    def test_year_and_month_match_reference(self):
        ref = date(2026, 8, 8)
        result = get_last_30_days(reference_date=ref)
        entry = result[0]
        assert entry["year"] == 2026
        assert entry["month"] == 8

    def test_defaults_to_today(self):
        result = get_last_30_days()
        entry = result[0]
        today = date.today()
        assert entry["year"] == today.year
        assert entry["month"] == today.month
