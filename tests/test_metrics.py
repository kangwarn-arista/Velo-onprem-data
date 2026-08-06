"""Tests for metrics.py pure computation functions.

Covers: get_target_months, bytes_to_mbps, percentile_95.
No VCO credentials needed -- metrics.py uses only stdlib.
"""
from datetime import date

import pytest

from metrics import bytes_to_mbps, get_target_months, percentile_95


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
        # 2026-07-01T00:00:00 UTC = 1782950400 seconds
        expected_start_ms = 1782950400 * 1000
        assert result[0]["start_ms"] == expected_start_ms

    def test_single_month_end_ms_is_next_month_start(self):
        """end_ms for July 2026 is 2026-08-01T00:00:00 UTC in milliseconds."""
        result = get_target_months(1, date(2026, 8, 5))
        # 2026-08-01T00:00:00 UTC = 1785628800 seconds
        expected_end_ms = 1785628800 * 1000
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
