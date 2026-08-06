"""CLI argument parsing tests for vco_edge_export.build_parser.

Overwrites VCO_TOKEN and VCO_URL environment variables before importing
vco_edge_export so the module-level load_dotenv() and os.getenv() calls
never use real credentials.
"""
import os

import pytest

os.environ["VCO_TOKEN"] = "Token test"
os.environ["VCO_URL"] = "https://test.example.com/portal/"

from vco_edge_export import build_parser  # noqa: E402


def test_default_values():
    """parse_args([]) yields collect_95th=False and months=1."""
    parser = build_parser()
    args = parser.parse_args([])
    assert args.collect_95th is False
    assert args.months == 1


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


def test_help_contains_flags():
    """parser.format_help() contains both --collect_95th and --months."""
    parser = build_parser()
    help_text = parser.format_help()
    assert "--collect_95th" in help_text
    assert "--months" in help_text
