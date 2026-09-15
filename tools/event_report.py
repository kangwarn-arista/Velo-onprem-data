"""Standalone CLI to export enterprise events from VCO via JSON-RPC 2.0.

Reuses the same auth/JSON-RPC/retry/error conventions as vco_edge_export.py
without importing from it — keeping this tool independently runnable.

Usage:
    uv run python tools/event_report.py [--days N] [--vco-host HOST] [--vco-token TOKEN]
    uv run python tools/event_report.py --help
"""
__version__ = "0.1.0"

import argparse
import csv
import json
import logging
import os
import sys
import time
import urllib3
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from requests.structures import CaseInsensitiveDict

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load .env file from the directory where the binary/script lives
_script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
load_dotenv(os.path.join(_script_dir, ".env"))

# Read variables from .env
token = os.getenv("VCO_TOKEN")
vco_host = os.getenv("VCO_HOST", "localhost")
vco_url = None


class VCOAuthError(Exception):
    """Raised when VCO returns an authentication or authorization error."""
    pass


def normalize_token(raw_token: str) -> str:
    """Ensure the required 'Token ' prefix is present for the VCO Authorization header.

    Idempotent: if the token already starts with 'Token ', it is returned
    unchanged. This prevents the double-prefix bug ('Token Token <value>')
    that occurs when users copy a token string that already includes the prefix.

    Args:
        raw_token: The raw API token string from the environment variable or
            CLI argument. May or may not include the 'Token ' prefix.

    Returns:
        The token string with exactly one 'Token ' prefix.

    Raises:
        ValueError: If ``raw_token`` is empty or falsy.
    """
    if not raw_token:
        raise ValueError("raw_token must be a non-empty string")
    if raw_token.startswith("Token "):
        return raw_token
    return f"Token {raw_token}"


def api_call(method, params, max_retries=5):
    """Make a JSON-RPC 2.0 POST request to the VCO portal endpoint.

    Args:
        method: JSON-RPC method name (e.g. 'event/getEnterpriseEvents').
        params: Dict of parameters to pass to the method.
        max_retries: Maximum number of retry attempts for transient errors.

    Returns:
        Parsed JSON response dict, or {} on non-auth errors.

    Raises:
        VCOAuthError: On HTTP 401/403 or JSON-RPC auth-keyword errors.
    """
    headers = CaseInsensitiveDict()
    headers["Authorization"] = token
    headers["Content-Type"] = "application/json"

    data = {"id": 0, "jsonrpc": "2.0", "method": method, "params": params}

    resp = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                vco_url, headers=headers, data=json.dumps(data), verify=False
            )

            if resp.status_code in (401, 403):
                raise VCOAuthError(
                    f"Authentication failed (HTTP {resp.status_code}). "
                    f"Check that VCO_TOKEN in .env is valid and not expired."
                )

            if resp.status_code == 429:
                try:
                    retry_after = int(resp.headers.get("Retry-After", 2 ** attempt))
                except (ValueError, TypeError):
                    retry_after = 2 ** attempt
                logging.warning(
                    "Rate limited (429) on %s, retrying in %ds (attempt %d/%d)",
                    method, retry_after, attempt + 1, max_retries,
                )
                time.sleep(retry_after)
                continue

            resp.raise_for_status()
            result = resp.json()

            if "error" in result:
                error_msg = result["error"]
                if isinstance(error_msg, dict):
                    error_msg = error_msg.get("message", str(error_msg))
                # Only raise VCOAuthError for known auth error patterns
                auth_keywords = ["authentication", "unauthorized", "token", "permission"]
                if any(kw in str(error_msg).lower() for kw in auth_keywords):
                    raise VCOAuthError(
                        f"VCO API rejected request to '{method}': {error_msg}. "
                        f"This typically indicates an invalid or expired token."
                    )
                # For non-auth JSON-RPC errors, log and return empty dict
                logging.error("API Error on '%s': %s", method, error_msg)
                return {}

            return result

        except VCOAuthError:
            raise
        except requests.exceptions.HTTPError as e:
            if resp is not None and resp.status_code >= 500 and attempt < max_retries - 1:
                wait = 2 ** attempt
                logging.warning(
                    "Server error %s on %s, retrying in %ds (%d/%d)",
                    resp.status_code, method, wait, attempt + 1, max_retries,
                )
                time.sleep(wait)
                continue
            logging.error("API Error: %s", e)
            return {}
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                logging.warning(
                    "Network error on %s, retrying in %ds (%d/%d): %s",
                    method, wait, attempt + 1, max_retries, e,
                )
                time.sleep(wait)
                continue
            logging.error("API Error: %s", e)
            return {}
        except Exception as e:
            logging.error("API Error: %s", e)
            return {}

    logging.error("API Error: max retries exceeded for %s", method)
    return {}


def get_enterprise_ids() -> list:
    """Fetch all enterprises from the VCO network.

    Calls network/getNetworkEnterprises and maps results to dicts with
    id, name, and logicalId fields.

    Returns:
        List of dicts with keys: id, name, logicalId.
    """
    method = "network/getNetworkEnterprises"
    params = {"networkId": 1, "with": ["edges"]}

    parsed = api_call(method, params)
    return [
        {
            "id": item.get("id"),
            "name": item.get("name"),
            "logicalId": item.get("logicalId", ""),
        }
        for item in parsed.get("result", [])
    ]


def get_enterprise_events(enterprise_id: int, start_ms: int, end_ms: int, limit: int = 2048) -> dict:
    """Fetch enterprise events from VCO via event/getEnterpriseEvents.

    Args:
        enterprise_id: The VCO enterprise ID to query.
        start_ms: Interval start timestamp in UTC milliseconds since epoch.
        end_ms: Interval end timestamp in UTC milliseconds since epoch.
        limit: Maximum number of events to retrieve (default: 2048).

    Returns:
        Full parsed JSON-RPC response dict. Event data is at result["data"]
        on real VCO responses.
    """
    method = "event/getEnterpriseEvents"
    params = {
        "enterpriseId": enterprise_id,
        "interval": {"start": start_ms, "end": end_ms},
        "limit": limit,
    }
    return api_call(method, params)


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser for VCO event report.

    Returns:
        Configured ArgumentParser with credential + time-window flags.
    """
    parser = argparse.ArgumentParser(
        description="Export enterprise events from VCO via JSON-RPC event/getEnterpriseEvents."
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--vco-host",
        type=str,
        default=None,
        help="VCO hostname (e.g. vco.example.com). Overrides VCO_HOST in .env.",
    )
    parser.add_argument(
        "--vco-token",
        type=str,
        default=None,
        help="VCO API token. Overrides VCO_TOKEN in .env.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Days of event history to fetch (default: 7)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output CSV path (default: vco_events_{timestamp}.csv in current directory)",
    )
    parser.add_argument(
        "--enterprise-ids",
        type=int,
        nargs="+",
        default=None,
        metavar="ID",
        help="Only fetch events for enterprises with these numeric IDs.",
    )
    return parser


def compute_interval_ms(days: int, now: datetime = None) -> tuple:
    """Compute start/end timestamps in milliseconds for the given window.

    Pure helper — no side effects, directly testable.

    Args:
        days: Number of days of history to include.
        now: Reference datetime (default: datetime.now(tz=timezone.utc)).

    Returns:
        Tuple of (start_ms, end_ms) as integer milliseconds since epoch.
    """
    if now is None:
        now = datetime.now(tz=timezone.utc)
    end_ms = int(now.timestamp() * 1000)
    start_ms = end_ms - days * 86_400_000
    return start_ms, end_ms


def write_events_csv(rows: list, output_path: str) -> str:
    """Write event rows to a CSV file.

    Args:
        rows: List of event dicts. If empty, writes header-only CSV.
        output_path: Destination file path.

    Returns:
        The output_path that was written.
    """
    default_fields = [
        "id", "eventTime", "event", "category", "severity",
        "enterpriseId", "enterpriseName", "edgeName", "message", "detail",
    ]

    if not rows:
        fieldnames = default_fields
    else:
        # Union of keys in first-seen order across all rows
        seen = {}
        for row in rows:
            for key in row:
                if key not in seen:
                    seen[key] = True
        fieldnames = list(seen.keys())

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    return output_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    args = build_parser().parse_args()

    # Resolve token: CLI overrides env
    if args.vco_token:
        token = args.vco_token
    if not token:
        print("ERROR: VCO_TOKEN not found. Set VCO_TOKEN in .env or use --vco-token.")
        sys.exit(1)

    # Resolve host: CLI overrides env
    if args.vco_host:
        vco_host = args.vco_host
    if not vco_host:
        print("ERROR: VCO_HOST not found. Set VCO_HOST in .env or use --vco-host.")
        sys.exit(1)

    token = normalize_token(token)
    vco_url = f"https://{vco_host}/portal/"

    start_ms, end_ms = compute_interval_ms(args.days)

    try:
        enterprises = get_enterprise_ids()
    except VCOAuthError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    if not enterprises:
        print(
            "ERROR: No enterprises returned from VCO. "
            "This usually means the API token is invalid, expired, "
            "or lacks permissions. Verify VCO_TOKEN in .env."
        )
        sys.exit(1)

    print(f"Found {len(enterprises)} enterprises")

    if args.enterprise_ids:
        filter_set = set(args.enterprise_ids)
        enterprises = [e for e in enterprises if e["id"] in filter_set]
        if not enterprises:
            print("ERROR: No enterprises matched the provided --enterprise-ids.")
            sys.exit(1)
        print(f"Filtered to {len(enterprises)} enterprises by ID")

    all_rows = []
    for ent in enterprises:
        print(f"Fetching events for: {ent['name']} (id={ent['id']})")
        resp = get_enterprise_events(ent["id"], start_ms, end_ms)

        # Defensive: handle both {"result": {"data": [...]}} and {"result": [...]}
        result = resp.get("result", {})
        if isinstance(result, dict):
            data = result.get("data") or []
        elif isinstance(result, list):
            data = result
        else:
            data = []

        for row in data:
            row["enterpriseId"] = ent["id"]
            row["enterpriseName"] = ent["name"]
            all_rows.append(row)

        print(f"  {len(data)} events")

    output_path = args.output or f"vco_events_{datetime.now(tz=timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    write_events_csv(all_rows, output_path)
    print(f"Done. Wrote {len(all_rows)} events to {output_path}")
