"""Tests for tools/event_report.py CLI, pure helpers, and JSON-RPC wrappers.

VCO_TOKEN and VCO_HOST are set by conftest.py before this module is imported,
so tools.event_report's module-level os.getenv() calls use test credentials.
All HTTP is mocked — no live VCO required.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from tools.event_report import (
    build_parser,
    compute_interval_ms,
    write_events_csv,
    get_enterprise_events,
    get_enterprise_ids,
    api_call,
    VCOAuthError,
)


# ── CLI parsing ──────────────────────────────────────────────────────────


def test_default_values():
    """parse_args([]) yields days=7, vco_host/vco_token/output/enterprise_ids all None."""
    parser = build_parser()
    args = parser.parse_args([])
    assert args.days == 7
    assert args.vco_host is None
    assert args.vco_token is None
    assert args.output is None
    assert args.enterprise_ids is None


def test_days_custom():
    """--days 30 yields days=30."""
    parser = build_parser()
    args = parser.parse_args(["--days", "30"])
    assert args.days == 30


def test_days_invalid_type():
    """--days abc raises SystemExit (argparse type=int validation)."""
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--days", "abc"])


def test_vco_host_flag():
    """--vco-host vco.example.com yields vco_host='vco.example.com'."""
    parser = build_parser()
    args = parser.parse_args(["--vco-host", "vco.example.com"])
    assert args.vco_host == "vco.example.com"


def test_vco_token_flag():
    """--vco-token 'Token abc123' yields vco_token='Token abc123'."""
    parser = build_parser()
    args = parser.parse_args(["--vco-token", "Token abc123"])
    assert args.vco_token == "Token abc123"


def test_output_flag():
    """--output /tmp/x.csv yields output='/tmp/x.csv'."""
    parser = build_parser()
    args = parser.parse_args(["--output", "/tmp/x.csv"])
    assert args.output == "/tmp/x.csv"


def test_enterprise_ids_flag():
    """--enterprise-ids 1 2 3 yields enterprise_ids=[1, 2, 3]."""
    parser = build_parser()
    args = parser.parse_args(["--enterprise-ids", "1", "2", "3"])
    assert args.enterprise_ids == [1, 2, 3]


def test_help_contains_flags():
    """parser.format_help() contains all documented flags."""
    parser = build_parser()
    help_text = parser.format_help()
    assert "--vco-host" in help_text
    assert "--vco-token" in help_text
    assert "--days" in help_text
    assert "--output" in help_text


# ── compute_interval_ms ──────────────────────────────────────────────────


def test_compute_interval_ms_default_seven_days():
    """Default window spans exactly 7 days in milliseconds."""
    start, end = compute_interval_ms(7)
    assert end - start == 7 * 86_400_000


def test_compute_interval_ms_custom_days():
    """Window for days=30 spans exactly 30 days in milliseconds."""
    start, end = compute_interval_ms(30)
    assert end - start == 30 * 86_400_000


def test_compute_interval_ms_uses_provided_now():
    """Passing an explicit now produces exact millisecond math."""
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end_expected = int(now.timestamp() * 1000)
    start_expected = end_expected - 7 * 86_400_000
    start, end = compute_interval_ms(7, now=now)
    assert start == start_expected
    assert end == end_expected


# ── write_events_csv ─────────────────────────────────────────────────────


def test_write_events_csv_empty_rows_writes_header_only(tmp_path):
    """Empty rows list produces a CSV with one header line, including id and event columns."""
    out = str(tmp_path / "events.csv")
    write_events_csv([], out)
    with open(out, newline="") as f:
        lines = f.readlines()
    assert len(lines) == 1, "Expected exactly one header line for empty rows"
    assert "id" in lines[0]
    assert "event" in lines[0]


def test_write_events_csv_writes_union_of_keys(tmp_path):
    """Union of keys across all rows becomes the header; all rows are written."""
    rows = [{"a": 1, "b": 2}, {"b": 3, "c": 4}]
    out = str(tmp_path / "events.csv")
    write_events_csv(rows, out)
    with open(out, newline="") as f:
        lines = f.readlines()
    header = lines[0]
    assert "a" in header
    assert "b" in header
    assert "c" in header
    # header + 2 data rows
    assert len(lines) == 3


# ── get_enterprise_events ────────────────────────────────────────────────


def test_get_enterprise_events_params():
    """get_enterprise_events calls api_call with the correct method and params."""
    with patch("tools.event_report.api_call") as mock_api_call:
        mock_api_call.return_value = {}
        get_enterprise_events(42, 1_000, 2_000)
        mock_api_call.assert_called_once()
        method = mock_api_call.call_args[0][0]
        params = mock_api_call.call_args[0][1]
        assert method == "event/getEnterpriseEvents"
        assert params["enterpriseId"] == 42
        assert params["interval"] == {"start": 1_000, "end": 2_000}
        assert params["limit"] == 2048


def test_get_enterprise_events_custom_limit():
    """Passing limit=100 results in params['limit'] == 100."""
    with patch("tools.event_report.api_call") as mock_api_call:
        mock_api_call.return_value = {}
        get_enterprise_events(1, 0, 1000, limit=100)
        params = mock_api_call.call_args[0][1]
        assert params["limit"] == 100


def test_get_enterprise_events_returns_api_result():
    """get_enterprise_events returns the api_call result unchanged."""
    canned = {"result": {"data": [{"id": 1}, {"id": 2}]}}
    with patch("tools.event_report.api_call") as mock_api_call:
        mock_api_call.return_value = canned
        result = get_enterprise_events(1, 0, 1000)
        assert result == canned


# ── get_enterprise_ids ───────────────────────────────────────────────────


def test_get_enterprise_ids_shape():
    """get_enterprise_ids maps api_call result to id/name/logicalId dicts."""
    canned = {"result": [{"id": 1, "name": "Ent1", "logicalId": "abc"}]}
    with patch("tools.event_report.api_call") as mock_api_call:
        mock_api_call.return_value = canned
        result = get_enterprise_ids()
        assert result == [{"id": 1, "name": "Ent1", "logicalId": "abc"}]


# ── api_call auth errors ─────────────────────────────────────────────────


def test_api_call_raises_vco_auth_error_on_401():
    """HTTP 401 response causes api_call to raise VCOAuthError."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.headers = {}
    mock_resp.json.return_value = {}
    with patch("tools.event_report.requests.post", return_value=mock_resp):
        with pytest.raises(VCOAuthError):
            api_call("x", {})


def test_api_call_returns_empty_on_generic_http_error():
    """Non-auth HTTP errors (e.g. 400) return {} without raising."""
    import requests as req

    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.headers = {}
    http_error = req.exceptions.HTTPError("400 Client Error")
    mock_resp.raise_for_status.side_effect = http_error
    with patch("tools.event_report.requests.post", return_value=mock_resp):
        result = api_call("x", {})
        assert result == {}
