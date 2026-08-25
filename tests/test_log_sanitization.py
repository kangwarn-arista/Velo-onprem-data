"""Tests for log sanitization and metadata stripping.

Verifies that build_output_metadata returns only the three allowed keys
(version, vco_host, generated_at) and excludes all sensitive collection
parameters that were previously included in the metadata dict.
"""
import pytest

from output import build_output_metadata


_SAMPLE_ARGS = ("1.4", "vco.test.com", "20260822_120000")

_FORBIDDEN_KEYS = [
    "months",
    "edges",
    "edge_month_records",
    "last_30_days",
    "all_metrics",
    "enterprises",
]


class TestBuildOutputMetadata:
    """Tests for the build_output_metadata sanitization helper."""

    def test_returns_only_allowed_keys(self):
        """Returned dict contains exactly the three allowed keys."""
        meta = build_output_metadata(*_SAMPLE_ARGS)
        assert set(meta.keys()) == {"version", "vco_host", "generated_at"}

    def test_values_match_inputs(self):
        """Returned values correspond to the input arguments."""
        meta = build_output_metadata(*_SAMPLE_ARGS)
        assert meta["version"] == "1.4"
        assert meta["vco_host"] == "vco.test.com"
        assert meta["generated_at"] == "20260822_120000"

    @pytest.mark.parametrize("forbidden_key", _FORBIDDEN_KEYS)
    def test_excludes_forbidden_key(self, forbidden_key: str):
        """Sensitive collection parameter is absent from the returned dict."""
        meta = build_output_metadata(*_SAMPLE_ARGS)
        assert forbidden_key not in meta

    def test_includes_vco_version_when_provided(self):
        """vco_version appears in the dict when explicitly passed."""
        meta = build_output_metadata(*_SAMPLE_ARGS, vco_version="6.4.2.5")
        assert meta["vco_version"] == "6.4.2.5"
        assert "version" in meta

    def test_includes_vco_build_when_provided(self):
        """vco_build appears in the dict when explicitly passed."""
        meta = build_output_metadata(
            *_SAMPLE_ARGS,
            vco_build="R6135-20260803-0930-GA-9af6dfb8fe",
        )
        assert meta["vco_build"] == "R6135-20260803-0930-GA-9af6dfb8fe"

    def test_includes_both_vco_version_and_build(self):
        """Both vco_version and vco_build appear when provided together."""
        meta = build_output_metadata(
            *_SAMPLE_ARGS,
            vco_version="6.4.2.5",
            vco_build="R6135-20260803-0930-GA-9af6dfb8fe",
        )
        assert set(meta.keys()) == {
            "version", "vco_host", "generated_at",
            "vco_version", "vco_build",
        }

    def test_omits_vco_version_when_none(self):
        """vco_version key is absent when passed as None (default)."""
        meta = build_output_metadata(*_SAMPLE_ARGS, vco_version=None)
        assert "vco_version" not in meta

    def test_omits_vco_build_when_none(self):
        """vco_build key is absent when passed as None (default)."""
        meta = build_output_metadata(*_SAMPLE_ARGS, vco_build=None)
        assert "vco_build" not in meta
