__version__ = "1.3"

import argparse
import io
import json
import logging
import shutil
import subprocess
import sys
import time
from datetime import datetime
import urllib3
import requests
import pandas as pd

from dotenv import load_dotenv
from requests.structures import CaseInsensitiveDict
import os

from metrics import (
    get_last_30_days,
    get_target_months,
    compute_daily_p95s,
    compute_edge_month_metrics,
    diagnose_edge_metrics,
    max_samples_for_month,
    SAMPLES_PER_DAY,
    validate_sample_count,
)
from output import write_month_csvs, write_combined_csv, create_zip_archive, create_encrypted_archive, build_output_metadata, apply_federal_redaction

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load .env file from the directory where the binary/script lives
_script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
load_dotenv(os.path.join(_script_dir, ".env"))

# Read variables from .env
token = os.getenv("VCO_TOKEN")
vco_host = os.getenv("VCO_HOST", "localhost")
vco_url = None

def _resolve_version() -> str:
    """Return version from the nearest git tag, stripping the leading 'v'.

    Falls back to ``__version__`` when git is unavailable (e.g. compiled
    binary) or the working directory is outside a repository.
    """
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=_script_dir,
        )
        if result.returncode == 0:
            tag = result.stdout.strip()
            return tag.lstrip("v") if tag else __version__
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return __version__


VERSION = _resolve_version()

OUTPUT_CSV = "vco_edge_export.csv"


class VCOAuthError(Exception):
    pass


def api_call(method, params, max_retries=5):
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
                logging.warning("Rate limited (429) on %s, retrying in %ds (attempt %d/%d)",
                                method, retry_after, attempt + 1, max_retries)
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


def get_enterprise_ids():
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


def get_edges(ent):

    method = "enterprise/getEnterpriseEdgeList"

    params = {
        "enterpriseId": ent["id"],
        "with": [
            "site",
            "ha",
            "configuration",
            "recentLinks",
            "cloudServices",
            "nvsFromEdge",
            "vnfs",
            "certificateSummary",
        ],
        "sortBy": [{"attribute": "edgeState", "type": "ASC"}],
        "_filterSpec": True,
    }

    return api_call(method, params)


def get_network_license_export() -> dict:
    """Fetch the network-wide license CSV export from VCO.

    Calls the license/exportNetworkEdgeLicenseData JSON-RPC method to retrieve
    a CSV string containing all edge license data across the network. The CSV
    data is available in the response at result.csv.

    Returns:
        The full parsed JSON-RPC response dict. The CSV string is at
        response["result"]["csv"]. Returns an empty dict on API error.
    """
    method = "license/exportNetworkEdgeLicenseData"
    params = {"networkId": 1}
    return api_call(method, params)


def get_edge_link_series(
    enterprise_id: int,
    edge_id: int,
    start_ms: int,
    end_ms: int,
    max_samples: int,
    *,
    include_peak_metrics: bool = False,
) -> dict:
    """Fetch per-edge link bandwidth time-series data from VCO.

    Calls the metrics/getEdgeLinkSeries JSON-RPC method to retrieve
    bytesTx and bytesRx samples for all links on a given edge within
    the specified time interval.

    Args:
        enterprise_id: The VCO enterprise ID that owns the edge.
        edge_id: The numeric edge ID (the ``id`` field, not ``logicalId``).
        start_ms: Interval start timestamp in UTC milliseconds since epoch.
        end_ms: Interval end timestamp in UTC milliseconds since epoch.
        max_samples: Maximum number of 5-minute samples to request.
            Computed as ``days_in_month × 288``.
        include_peak_metrics: When ``True``, also request
            ``maxIntervalBpsTx``, ``maxIntervalBpsRx``,
            ``minIntervalBpsTx``, and ``minIntervalBpsRx``.
            Requires VCO >= 6.4.

    Returns:
        The full parsed JSON-RPC response dict. The link series data is at
        response["result"]. Returns an empty dict on API error.
    """
    method = "metrics/getEdgeLinkSeries"
    metrics = ["bytesTx", "bytesRx"]
    if include_peak_metrics:
        metrics.extend([
            "maxIntervalBpsTx", "maxIntervalBpsRx",
            "minIntervalBpsTx", "minIntervalBpsRx",
        ])
    params = {
        "enterpriseId": enterprise_id,
        "edgeId": edge_id,
        "interval": {"start": start_ms, "end": end_ms},
        "maxSamples": max_samples,
        "metrics": metrics,
    }
    return api_call(method, params)


def get_vco_version() -> dict:
    """Fetch VCO software version and build info via the system/getVersionInfo REST API.

    Makes a POST request to ``/portal/rest/system/getVersionInfo`` and
    returns the ``version`` and ``build`` fields from the response.

    Returns:
        Dict with ``version`` (e.g. ``"6.4.2.5"``) and ``build``
        (e.g. ``"R6135-20260803-0930-GA-9af6dfb8fe"``).  Both values
        are ``None`` when the call fails.
    """
    headers = CaseInsensitiveDict()
    headers["Authorization"] = token
    headers["Content-Type"] = "application/json"

    try:
        resp = requests.post(
            f"https://{vco_host}/portal/rest/system/getVersionInfo",
            headers=headers,
            data="{}",
            verify=False,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "version": data.get("version"),
            "build": data.get("build"),
        }
    except Exception as e:
        logging.warning("Failed to detect VCO version: %s", e)
        return {"version": None, "build": None}


def parse_version_tuple(version_str: str) -> tuple[int, ...]:
    """Parse a dotted version string into a tuple of integers.

    Args:
        version_str: Version string such as ``"6.4.2.5"``.

    Returns:
        Tuple of integers, e.g. ``(6, 4, 2, 5)``.

    Raises:
        ValueError: If any segment is not a valid integer.
    """
    return tuple(int(x) for x in version_str.split("."))


def vco_supports_peak_metrics(version_str: str) -> bool:
    """Return True if the VCO version supports peak BPS metrics (>= 6.4)."""
    try:
        parts = parse_version_tuple(version_str)
        return len(parts) >= 2 and (parts[0], parts[1]) >= (6, 4)
    except (ValueError, IndexError):
        return False


def normalize_token(raw_token: str) -> str:
    """Ensure the required 'Token ' prefix is present for the VCO Authorization header.

    Idempotent: if the token already starts with 'Token ', it is returned
    unchanged.  This prevents the double-prefix bug ('Token Token <value>')
    that occurs when users copy a token string that already includes the prefix.

    Args:
        raw_token: The raw API token string from the environment variable or
            CLI argument.  May or may not include the 'Token ' prefix.

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


def package_and_cleanup(
    output_dir: str,
    zip_filename: str,
    metadata: dict,
    *,
    obfuscation_mode: str = "1",
) -> str:
    """Archive CSV files from output_dir into a zip and remove the source directory.

    Three-mode routing via ``obfuscation_mode``:

    - ``"2"`` — creates a Fernet-encrypted archive (``data.enc``
      payload inside the zip).
    - All other values (including ``"0"``, ``"1"``) — creates a plain
      zip archive with CSV files directly inside.

    The source ``output_dir`` is removed after successful archive creation.
    If archive creation fails, the source directory is preserved so that
    data can be recovered without re-collecting from the API.

    Args:
        output_dir: Path to the directory containing CSV files to archive.
        zip_filename: Destination path for the output zip file.
        metadata: Dict written as ``_metadata.json`` inside the archive.
        obfuscation_mode: Output mode string (default ``"1"``).

    Returns:
        The ``zip_filename`` string that was passed in.
    """
    if obfuscation_mode == "2":
        result = create_encrypted_archive(output_dir, zip_filename, metadata=metadata)
    else:
        result = create_zip_archive(output_dir, zip_filename, metadata=metadata)
    try:
        shutil.rmtree(output_dir)
    except OSError as exc:
        logging.warning(
            "Failed to remove temp directory %s: %s",
            output_dir,
            exc,
        )
    return result


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser for VCO edge export.

    Returns:
        argparse.ArgumentParser: Configured parser with --vco-host, --vco-token, and --months flags.
    """
    parser = argparse.ArgumentParser(
        description="Export VCO edge and license data with 95th percentile bandwidth metrics."
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
    )
    parser.add_argument(
        "--vco-host",
        type=str,
        default=None,
        help="VCO hostname (e.g. veco12-kiad1.velocloud.net). Overrides VCO_HOST in .env.",
    )
    parser.add_argument(
        "--vco-token",
        type=str,
        default=None,
        help="VCO API token. Overrides VCO_TOKEN in .env.",
    )
    time_group = parser.add_mutually_exclusive_group()
    time_group.add_argument(
        "--months",
        type=int,
        default=3,
        help=argparse.SUPPRESS,
    )
    time_group.add_argument(
        "--last_30_days",
        action="store_true",
        default=False,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--all_metrics",
        action="store_true",
        default=False,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--strict_validation",
        action="store_true",
        default=False,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--diagnose",
        type=str,
        default=None,
        metavar="EDGE_NAME",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--federal",
        action="store_true",
        default=False,
        help="Redact sensitive customer and partner fields from output CSVs.",
    )
    ent_group = parser.add_mutually_exclusive_group()
    ent_group.add_argument(
        "--enterprise-ids",
        type=int,
        nargs="+",
        default=None,
        metavar="ID",
        help="Only include enterprises with these numeric IDs.",
    )
    ent_group.add_argument(
        "--enterprise-names",
        type=str,
        nargs="+",
        default=None,
        metavar="NAME",
        help="Only include enterprises whose name matches (case-insensitive).",
    )
    return parser


if __name__ == "__main__":

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    args = build_parser().parse_args()

    # Determine obfuscation mode once; used throughout to gate CSV writes and
    # route output functions.  Default "1" = field-level obfuscation (mode 1).
    obfuscation_mode = os.getenv("OBFUSCATED", "1")

    print(f"vco_edge_export v{VERSION}")

    # Resolve token: CLI overrides env
    if args.vco_token:
        token = args.vco_token
    if not token:
        print("ERROR: VCO_TOKEN not found. Set VCO_TOKEN in .env or use --vco-token.")
        sys.exit(1)

    # Resolve host: CLI overrides env
    if args.vco_host:
        vco_host = args.vco_host

    token = normalize_token(token)
    vco_url = f"https://{vco_host}/portal/"

    if not args.last_30_days and (args.months < 1 or args.months > 12):
        logging.error("--months must be between 1 and 12, got %d", args.months)
        sys.exit(1)

    # -- Detect VCO version --
    vco_version_info = get_vco_version()
    vco_version = vco_version_info["version"]
    vco_build = vco_version_info["build"]
    if vco_version:
        logging.info("VCO version: %s (build: %s)", vco_version, vco_build)
    else:
        logging.warning("Could not determine VCO version")
    peak_supported = vco_supports_peak_metrics(vco_version) if vco_version else False

    collect_95th = os.getenv("SKIP_95TH") != "1"

    try:
        enterprise_ids = get_enterprise_ids()
    except VCOAuthError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    if not enterprise_ids:
        print(
            "ERROR: No enterprises returned from VCO. "
            "This usually means the API token is invalid, expired, "
            "or lacks permissions. Verify VCO_TOKEN in .env."
        )
        sys.exit(1)

    print(f"Found {len(enterprise_ids)} enterprises")

    if args.enterprise_ids:
        filter_set = set(args.enterprise_ids)
        enterprise_ids = [e for e in enterprise_ids if e["id"] in filter_set]
        matched_ids = {e["id"] for e in enterprise_ids}
        missing = filter_set - matched_ids
        if missing:
            logging.warning("Enterprise IDs not found: %s", sorted(missing))
        if not enterprise_ids:
            print("ERROR: No enterprises matched the provided --enterprise-ids.")
            sys.exit(1)
        print(f"Filtered to {len(enterprise_ids)} enterprises by ID")
    elif args.enterprise_names:
        filter_names = {n.lower() for n in args.enterprise_names}
        enterprise_ids = [e for e in enterprise_ids if e["name"].lower() in filter_names]
        matched_names = {e["name"].lower() for e in enterprise_ids}
        missing = filter_names - matched_names
        if missing:
            logging.warning("Enterprise names not found: %s", sorted(missing))
        if not enterprise_ids:
            print("ERROR: No enterprises matched the provided --enterprise-names.")
            sys.exit(1)
        print(f"Filtered to {len(enterprise_ids)} enterprises by name")

    # -- License CSV Export --
    license_export_response = get_network_license_export()
    csv_string = (license_export_response.get("result") or {}).get("csv", "")

    if not csv_string:
        print("WARNING: No license CSV data returned from API")
        license_df = pd.DataFrame()
    else:
        license_df = pd.read_csv(io.StringIO(csv_string))

    print(f"License CSV: {license_df.shape[0]} rows, {license_df.shape[1]} columns")
    print(f"License CSV columns: {list(license_df.columns)}")

    if license_df.empty:
        print("WARNING: No license data available. Cannot produce merged output.")
        sys.exit(0)

    if (
        "Customer Name" not in license_df.columns
        or "Edge Name" not in license_df.columns
    ):
        print(
            f"ERROR: License CSV missing required column(s) for merge. "
            f"Available: {list(license_df.columns)}"
        )
        sys.exit(1)

    edge_status_rows = []
    edge_info_list = []

    for ent in enterprise_ids:

        print(f"\nFetching enterprise: {ent['name']} (id={ent['id']})")

        edges = get_edges(ent)

        edge_data = (edges.get("result") or {}).get("data", [])

        print(f"  Edges Found: {len(edge_data)}")

        for edge in edge_data:
            edge_status_rows.append(
                {
                    "Customer Name": ent["name"],
                    "Edge Name": edge.get("name", ""),
                    "Edge UUID": edge.get("logicalId", ""),
                    "Edge Status": edge.get("edgeState", ""),
                }
            )
            if collect_95th:
                edge_id = edge.get("id")
                if edge_id is not None:
                    edge_info_list.append(
                        {
                            "enterprise_id": ent["id"],
                            "enterprise_name": ent["name"],
                            "edge_id": edge_id,
                            "edge_name": edge.get("name", ""),
                        }
                    )
                else:
                    logging.warning(
                        "Edge '%s' has no numeric id -- skipping metrics",
                        edge.get("name", "unknown"),
                    )

    edge_status_df = pd.DataFrame(
        edge_status_rows,
        columns=["Customer Name", "Edge Name", "Edge UUID", "Edge Status"],
    )
    print(
        f"Edge status data: {len(edge_status_df)} edges collected across all enterprises"
    )

    before_dedup = len(edge_status_df)
    edge_status_df = edge_status_df.drop_duplicates(
        subset=["Customer Name", "Edge Name"], keep="first"
    )
    dropped_count = before_dedup - len(edge_status_df)
    if dropped_count > 0:
        print(
            f"WARNING: {dropped_count} duplicate (Customer Name, Edge Name) "
            f"pairs removed from edge status data"
        )

    merged_df = license_df.merge(
        edge_status_df[["Customer Name", "Edge Name", "Edge UUID", "Edge Status"]],
        on=["Customer Name", "Edge Name"],
        how="left",
    )

    unmatched_mask = merged_df["Edge Status"].isna()
    unmatched_count = unmatched_mask.sum()
    matched_count = len(merged_df) - unmatched_count

    if unmatched_count > 0:
        print(f"WARNING: {unmatched_count} license rows have no matching edge status:")
        for _, row in merged_df[unmatched_mask].head(20).iterrows():
            print(
                f"  Customer Name: {row['Customer Name']}, Edge Name: {row['Edge Name']}"
            )
        if unmatched_count > 20:
            print(f"  ... and {unmatched_count - 20} more")

    merged_df["Edge UUID"] = merged_df["Edge UUID"].fillna("")
    merged_df["Edge Status"] = merged_df["Edge Status"].fillna("")

    if obfuscation_mode != "1":
        output_df = merged_df.copy()
        if args.federal:
            apply_federal_redaction(output_df)
        output_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
        print(
            f"Done. {len(merged_df)} rows written to '{OUTPUT_CSV}' "
            f"({matched_count} matched, {unmatched_count} unmatched)"
        )

    # -- Diagnose mode --
    if args.diagnose:
        target_name = args.diagnose.strip()
        logging.info("Diagnose mode: searching for edge '%s'", target_name)

        # Find the edge across all enterprises — collect all matches so we
        # can warn when multiple enterprises contain edges with the same name.
        matched_edges: list[dict] = []
        all_edge_names: list[str] = []
        for ent in enterprise_ids:
            edges = get_edges(ent)
            edge_data = (edges.get("result") or {}).get("data", [])
            for edge in edge_data:
                name = edge.get("name", "")
                all_edge_names.append(f"  {name} ({ent['name']})")
                if name.lower() == target_name.lower():
                    matched_edges.append({
                        "enterprise_id": ent["id"],
                        "enterprise_name": ent["name"],
                        "edge_id": edge.get("id"),
                        "edge_name": name,
                        "edge_state": edge.get("edgeState", "UNKNOWN"),
                        "serial_number": edge.get("serialNumber", ""),
                    })

        if not matched_edges:
            print(f"\nEdge '{target_name}' not found. Available edges:")
            for en in sorted(all_edge_names):
                print(en)
            sys.exit(1)

        if len(matched_edges) > 1:
            print(f"WARNING: {len(matched_edges)} edges match '{target_name}':")
            for me in matched_edges:
                print(
                    f"  {me['edge_name']} "
                    f"(enterprise: {me['enterprise_name']}, id: {me['edge_id']})"
                )
            print("Using the first match. Use a unique edge name to avoid ambiguity.")

        matched_edge = matched_edges[0]

        print(f"\n{'=' * 60}")
        print(f"DIAGNOSTIC REPORT: {matched_edge['edge_name']}")
        print(f"{'=' * 60}")
        print(f"  Enterprise : {matched_edge['enterprise_name']}")
        print(f"  Edge ID    : {matched_edge['edge_id']}")
        print(f"  State      : {matched_edge['edge_state']}")
        print(f"  Serial     : {matched_edge['serial_number']}")

        target_months = get_last_30_days() if args.last_30_days else get_target_months(args.months)
        for month in target_months:
            print(f"\n{'─' * 60}")
            print(f"Month: {month['label']}")
            print(f"{'─' * 60}")

            samples = (
                30 * SAMPLES_PER_DAY
                if args.last_30_days
                else max_samples_for_month(month["year"], month["month"])
            )
            print(f"  Expected samples: {samples}")

            response = get_edge_link_series(
                matched_edge["enterprise_id"],
                matched_edge["edge_id"],
                month["start_ms"],
                month["end_ms"],
                samples,
            )

            link_series = response.get("result") or []
            if not link_series:
                print("  API returned empty result — no link data.")
                if not response:
                    print("  (API call itself failed — check logs above)")
                elif "result" in response and response["result"] is None:
                    print("  (API returned null result)")
                continue

            diag = diagnose_edge_metrics(link_series)
            print(f"  Links found: {diag['link_count']}")

            for link_detail in diag["links"]:
                print(f"\n  Link ID: {link_detail['link_id']}")
                for m in link_detail["metrics"]:
                    status_parts = [f"samples={m['samples']}"]
                    if m["none_count"] > 0:
                        pct = m["none_count"] / m["samples"] * 100 if m["samples"] else 0
                        status_parts.append(f"null={m['none_count']} ({pct:.1f}%)")
                    if m["zero_count"] > 0:
                        pct = m["zero_count"] / m["samples"] * 100 if m["samples"] else 0
                        status_parts.append(f"zero={m['zero_count']} ({pct:.1f}%)")
                    print(f"    {m['name']}: {', '.join(status_parts)}")

            print(f"\n  Aggregated samples: {diag['total_samples_after_aggregation']}")
            print(f"  All zeros: {diag['all_zero']}")

            if diag["all_zero"]:
                print("  >> No traffic data — metrics will be 0.0")
            else:
                daily_detail = compute_daily_p95s(link_series, month["start_ms"])
                daily_detail.sort(key=lambda d: d["total_p95"], reverse=True)

                print(f"\n  Daily P95 values ({len(daily_detail)} days):")
                print(f"  {'Date':<12} {'Samples':>7}  "
                      f"{'Tx Mbps':>10}  {'Rx Mbps':>10}  {'Total Mbps':>12}")
                print(f"  {'─' * 12} {'─' * 7}  "
                      f"{'─' * 10}  {'─' * 10}  {'─' * 12}")
                for day in daily_detail:
                    print(f"  {day['date']!s:<12} {day['sample_count']:>7}  "
                          f"{day['tx_p95']:>10.0f}  {day['rx_p95']:>10.0f}  "
                          f"{day['total_p95']:>12.0f}")

                metrics = compute_edge_month_metrics(link_series, month["start_ms"])
                print(f"\n  Monthly P95 (from {len(daily_detail)} daily P95 values):")
                print(f"    tx={metrics['monthly_tx_95th_mbps']:.0f}  "
                      f"rx={metrics['monthly_rx_95th_mbps']:.0f}  "
                      f"total={metrics['monthly_total_95th_mbps']:.0f} Mbps")

        print(f"\n{'=' * 60}")
        print("Diagnostic complete.")
        sys.exit(0)

    if collect_95th:
        seen_edges = set()
        deduped_edge_info_list = []
        for ei in edge_info_list:
            key = (ei["enterprise_id"], ei["edge_id"])
            if key not in seen_edges:
                seen_edges.add(key)
                deduped_edge_info_list.append(ei)
            else:
                logging.warning(
                    "Duplicate edge id=%s name='%s' — skipping duplicate metrics collection",
                    ei["edge_id"], ei["edge_name"],
                )
        edge_info_list = deduped_edge_info_list

        target_months = get_last_30_days() if args.last_30_days else get_target_months(args.months)
        metrics_results = []
        for edge_info in edge_info_list:
            print(
                f"\n  Processing edge: {edge_info['edge_name']} "
                f"({edge_info['enterprise_name']})"
            )
            for month in target_months:
                try:
                    samples = (
                        30 * SAMPLES_PER_DAY
                        if args.last_30_days
                        else max_samples_for_month(month["year"], month["month"])
                    )
                    response = get_edge_link_series(
                        edge_info["enterprise_id"],
                        edge_info["edge_id"],
                        month["start_ms"],
                        month["end_ms"],
                        samples,
                        include_peak_metrics=peak_supported,
                    )
                    link_series = response.get("result") or []
                    validation = validate_sample_count(
                        link_series, samples, strict=args.strict_validation,
                    )
                    if not validation["valid"]:
                        logging.warning(
                            "Sample count mismatch for edge %s month %s: %s",
                            edge_info["edge_name"],
                            month["label"],
                            validation["links"],
                        )
                    metrics = compute_edge_month_metrics(
                        link_series, month["start_ms"],
                        include_peak=peak_supported,
                    )
                    metrics_results.append(
                        {
                            "enterprise_name": edge_info["enterprise_name"],
                            "edge_name": edge_info["edge_name"],
                            "month_label": month["label"],
                            **metrics,
                        }
                    )
                except VCOAuthError:
                    raise
                except Exception as e:
                    logging.warning(
                        "Failed to collect metrics for edge %s (%s) month %s: %s",
                        edge_info["edge_name"],
                        edge_info["enterprise_name"],
                        month["label"],
                        e,
                    )
        if not metrics_results:
            print("No metrics data collected -- skipping output packaging")
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = f"{vco_host}_v{VERSION}_{timestamp}"
            os.makedirs(output_dir, exist_ok=True)
            if obfuscation_mode == "1":
                write_combined_csv(
                    merged_df, metrics_results, target_months, vco_host, output_dir,
                    include_peak=peak_supported,
                    federal=args.federal,
                )
            else:
                write_month_csvs(
                    merged_df, metrics_results, target_months, vco_host, output_dir,
                    all_metrics=args.all_metrics,
                    include_peak=peak_supported,
                    federal=args.federal,
                )
            zip_filename = f"{output_dir}.zip"
            metadata = build_output_metadata(
                VERSION, vco_host, timestamp,
                vco_version=vco_version, vco_build=vco_build,
            )
            package_and_cleanup(output_dir, zip_filename, metadata, obfuscation_mode=obfuscation_mode)
