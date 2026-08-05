"""Minimal failing test for build_parser — RED phase."""
import os

os.environ.setdefault("VCO_TOKEN", "Token test")
os.environ.setdefault("VCO_URL", "https://test.example.com/portal/")

from vco_edge_export import build_parser  # noqa: E402


def test_build_parser_returns_parser():
    """build_parser() must return an ArgumentParser."""
    import argparse
    parser = build_parser()
    assert isinstance(parser, argparse.ArgumentParser)
