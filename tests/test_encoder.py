"""TDD tests for encoder.py — Record Hash encoder module.

Tests verify:
- Output length is always 344 characters
- SENTINEL_HASH constant for empty/None UUID
- NaN metric handling (-1.0 sentinel in struct)
- Zero and max metric values
- UUID uniqueness (different UUIDs → different hashes)
- Determinism (same input → same output)
- last30d label handling
- STRUCT_FORMAT packs to exactly 256 bytes
- STRUCT_VERSION == 1
- At least 15 test cases total
"""

import base64
import math
import struct

import pytest

from encoder import (
    SENTINEL_HASH,
    STRUCT_FORMAT,
    STRUCT_VERSION,
    encode_record_hash,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_struct_version_is_1(self):
        assert STRUCT_VERSION == 1

    def test_struct_format_packs_to_256_bytes(self):
        assert struct.calcsize(STRUCT_FORMAT) == 256

    def test_sentinel_hash_is_344_chars(self):
        assert len(SENTINEL_HASH) == 344

    def test_sentinel_hash_is_all_zeros_encoded(self):
        expected = base64.b64encode(b"\x00" * 256).decode("ascii")
        assert SENTINEL_HASH == expected


# ---------------------------------------------------------------------------
# Empty / None UUID (sentinel path)
# ---------------------------------------------------------------------------


class TestSentinelPath:
    def test_empty_uuid_returns_sentinel_hash(self):
        data = [{"label": "07-2026", "95th": 100.0, "peak": 200.0}]
        result = encode_record_hash(data, "")
        assert result == SENTINEL_HASH

    def test_none_uuid_returns_sentinel_hash(self):
        data = [{"label": "07-2026", "95th": 100.0, "peak": 200.0}]
        result = encode_record_hash(data, None)
        assert result == SENTINEL_HASH

    def test_whitespace_only_uuid_returns_sentinel_hash(self):
        data = [{"label": "07-2026", "95th": 100.0, "peak": 200.0}]
        result = encode_record_hash(data, "   ")
        assert result == SENTINEL_HASH


# ---------------------------------------------------------------------------
# Output length (344 chars for all valid input shapes)
# ---------------------------------------------------------------------------


class TestOutputLength:
    UUID = "550e8400-e29b-41d4-a716-446655440000"

    def test_one_month_produces_344_chars(self):
        data = [{"label": "07-2026", "95th": 100.0, "peak": 200.0}]
        assert len(encode_record_hash(data, self.UUID)) == 344

    def test_three_months_produces_344_chars(self):
        data = [
            {"label": "05-2026", "95th": 10.0, "peak": 20.0},
            {"label": "06-2026", "95th": 30.0, "peak": 40.0},
            {"label": "07-2026", "95th": 50.0, "peak": 60.0},
        ]
        assert len(encode_record_hash(data, self.UUID)) == 344

    def test_twelve_months_max_produces_344_chars(self):
        data = [
            {"label": f"{m:02d}-2026", "95th": float(m * 10), "peak": float(m * 20)}
            for m in range(1, 13)
        ]
        assert len(encode_record_hash(data, self.UUID)) == 344

    def test_zero_months_empty_list_produces_344_chars(self):
        assert len(encode_record_hash([], self.UUID)) == 344


# ---------------------------------------------------------------------------
# NaN metric handling
# ---------------------------------------------------------------------------


class TestNaNHandling:
    UUID = "550e8400-e29b-41d4-a716-446655440000"

    def test_nan_95th_does_not_raise(self):
        data = [{"label": "07-2026", "95th": float("nan"), "peak": 200.0}]
        result = encode_record_hash(data, self.UUID)
        assert len(result) == 344

    def test_nan_peak_does_not_raise(self):
        data = [{"label": "07-2026", "95th": 100.0, "peak": float("nan")}]
        result = encode_record_hash(data, self.UUID)
        assert len(result) == 344

    def test_both_nan_produces_valid_hash(self):
        data = [{"label": "07-2026", "95th": float("nan"), "peak": float("nan")}]
        result = encode_record_hash(data, self.UUID)
        assert len(result) == 344

    def test_nan_and_zero_produce_different_hashes(self):
        uuid = self.UUID
        nan_data = [{"label": "07-2026", "95th": float("nan"), "peak": 0.0}]
        zero_data = [{"label": "07-2026", "95th": 0.0, "peak": 0.0}]
        assert encode_record_hash(nan_data, uuid) != encode_record_hash(zero_data, uuid)


# ---------------------------------------------------------------------------
# Specific metric value edge cases
# ---------------------------------------------------------------------------


class TestMetricValues:
    UUID = "550e8400-e29b-41d4-a716-446655440000"

    def test_zero_metric_values_produce_valid_hash(self):
        data = [{"label": "07-2026", "95th": 0.0, "peak": 0.0}]
        assert len(encode_record_hash(data, self.UUID)) == 344

    def test_large_metric_value_produces_valid_hash(self):
        data = [{"label": "07-2026", "95th": 100000.0, "peak": 200000.0}]
        assert len(encode_record_hash(data, self.UUID)) == 344

    def test_last30d_label_does_not_raise(self):
        data = [{"label": "last30d", "95th": 50.0, "peak": 100.0}]
        result = encode_record_hash(data, self.UUID)
        assert len(result) == 344


# ---------------------------------------------------------------------------
# Determinism and UUID uniqueness
# ---------------------------------------------------------------------------


class TestDeterminismAndUniqueness:
    def test_same_input_same_uuid_is_deterministic(self):
        data = [{"label": "07-2026", "95th": 100.0, "peak": 200.0}]
        uuid = "550e8400-e29b-41d4-a716-446655440000"
        result1 = encode_record_hash(data, uuid)
        result2 = encode_record_hash(data, uuid)
        assert result1 == result2

    def test_different_uuids_produce_different_hashes(self):
        data = [{"label": "07-2026", "95th": 100.0, "peak": 200.0}]
        uuid_a = "550e8400-e29b-41d4-a716-446655440000"
        uuid_b = "660e8400-e29b-41d4-a716-446655440001"
        assert encode_record_hash(data, uuid_a) != encode_record_hash(data, uuid_b)


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestErrorCases:
    UUID = "550e8400-e29b-41d4-a716-446655440000"

    def test_too_many_months_raises_value_error(self):
        data = [
            {"label": f"{m:02d}-2026", "95th": 0.0, "peak": 0.0}
            for m in range(1, 14)  # 13 months > MAX_MONTHS
        ]
        with pytest.raises(ValueError):
            encode_record_hash(data, self.UUID)
