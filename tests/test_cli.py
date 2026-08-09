"""CLI argument parsing tests for vco_edge_export.build_parser.

VCO_TOKEN and VCO_URL are set by conftest.py before this module is imported,
so vco_edge_export's module-level os.getenv() calls use test credentials.
"""
import pytest

from vco_edge_export import build_parser


def test_default_values():
    """parse_args([]) yields collect_95th=False, months=1, strict_validation=False."""
    parser = build_parser()
    args = parser.parse_args([])
    assert args.collect_95th is False
    assert args.months == 1
    assert args.strict_validation is False


def test_collect_95th_flag():
    """parse_args(["--collect_95th"]) yields collect_95th=True."""
    parser = build_parser()
    args = parser.parse_args(["--collect_95th"])
    assert args.collect_95th is True


def test_months_custom():
    """parse_args(["--months", "3"]) yields months=3."""
    parser = build_parser()
    args = parser.parse_args(["--months", "3"])
    assert args.months == 3


def test_combined_flags():
    """parse_args(["--collect_95th", "--months", "6"]) yields collect_95th=True, months=6."""
    parser = build_parser()
    args = parser.parse_args(["--collect_95th", "--months", "6"])
    assert args.collect_95th is True
    assert args.months == 6


def test_months_invalid_type():
    """parse_args(["--months", "abc"]) raises SystemExit (argparse type=int validation)."""
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--months", "abc"])


def test_strict_validation_flag():
    """parse_args(["--strict_validation"]) yields strict_validation=True."""
    parser = build_parser()
    args = parser.parse_args(["--strict_validation"])
    assert args.strict_validation is True


def test_diagnose_default_none():
    """parse_args([]) yields diagnose=None."""
    parser = build_parser()
    args = parser.parse_args([])
    assert args.diagnose is None


def test_diagnose_flag():
    """parse_args(["--diagnose", "WKEPRTR01"]) yields diagnose='WKEPRTR01'."""
    parser = build_parser()
    args = parser.parse_args(["--diagnose", "WKEPRTR01"])
    assert args.diagnose == "WKEPRTR01"


def test_last_30_days_default_false():
    """parse_args([]) yields last_30_days=False."""
    parser = build_parser()
    args = parser.parse_args([])
    assert args.last_30_days is False


def test_last_30_days_flag():
    """parse_args(["--last_30_days"]) yields last_30_days=True."""
    parser = build_parser()
    args = parser.parse_args(["--last_30_days"])
    assert args.last_30_days is True


def test_last_30_days_with_months_rejected():
    """parse_args(["--last_30_days", "--months", "3"]) raises SystemExit (mutually exclusive)."""
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--last_30_days", "--months", "3"])


def test_help_contains_flags():
    """parser.format_help() contains all expected flags."""
    parser = build_parser()
    help_text = parser.format_help()
    assert "--collect_95th" in help_text
    assert "--months" in help_text
    assert "--strict_validation" in help_text
    assert "--diagnose" in help_text
    assert "--last_30_days" in help_text
