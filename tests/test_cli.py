"""CLI argument parsing tests for vco_edge_export.build_parser.

VCO_TOKEN and VCO_HOST are set by conftest.py before this module is imported,
so vco_edge_export's module-level os.getenv() calls use test credentials.
"""
import pytest

from vco_edge_export import build_parser


def test_default_values():
    """parse_args([]) yields months=1, strict_validation=False, no overrides."""
    parser = build_parser()
    args = parser.parse_args([])
    assert args.months == 1
    assert args.strict_validation is False
    assert args.vco_host is None
    assert args.vco_token is None


def test_months_custom():
    """parse_args(["--months", "3"]) yields months=3."""
    parser = build_parser()
    args = parser.parse_args(["--months", "3"])
    assert args.months == 3


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


def test_vco_host_flag():
    """parse_args(["--vco-host", "vco.example.com"]) yields vco_host='vco.example.com'."""
    parser = build_parser()
    args = parser.parse_args(["--vco-host", "vco.example.com"])
    assert args.vco_host == "vco.example.com"


def test_vco_token_flag():
    """parse_args(["--vco-token", "Token abc123"]) yields vco_token='Token abc123'."""
    parser = build_parser()
    args = parser.parse_args(["--vco-token", "Token abc123"])
    assert args.vco_token == "Token abc123"


def test_help_contains_flags():
    """parser.format_help() contains all expected flags."""
    parser = build_parser()
    help_text = parser.format_help()
    assert "--vco-host" in help_text
    assert "--vco-token" in help_text
    assert "--months" in help_text
    assert "--strict_validation" in help_text
    assert "--diagnose" in help_text
    assert "--last_30_days" in help_text
