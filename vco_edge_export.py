import argparse
import io
import json
import logging
import time
import urllib3
import requests
import pandas as pd

from dotenv import load_dotenv
from requests.structures import CaseInsensitiveDict
import os

from metrics import get_target_months, compute_edge_month_metrics

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load .env file
load_dotenv()

# Read variables from .env
token = os.getenv("VCO_TOKEN")
vco_url = os.getenv("VCO_URL")
if vco_url and not vco_url.endswith("/"):
    vco_url += "/"

OUTPUT_CSV = "vco_edge_export.csv"


class VCOAuthError(Exception):
    pass


def api_call(method, params, max_retries=5):
    headers = CaseInsensitiveDict()
    headers["Authorization"] = token
    headers["Content-Type"] = "application/json"

    data = {"id": 0, "jsonrpc": "2.0", "method": method, "params": params}

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
                print(f"  Rate limited (429) on {method}, retrying in {retry_after}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_after)
                continue

            resp.raise_for_status()
            result = resp.json()

            if "error" in result:
                error_msg = result["error"]
                if isinstance(error_msg, dict):
                    error_code = error_msg.get("code", 0)
                    error_msg = error_msg.get("message", str(error_msg))
                else:
                    error_code = 0
                # Only raise VCOAuthError for known auth error patterns
                auth_keywords = ["authentication", "unauthorized", "token", "permission"]
                if any(kw in str(error_msg).lower() for kw in auth_keywords):
                    raise VCOAuthError(
                        f"VCO API rejected request to '{method}': {error_msg}. "
                        f"This typically indicates an invalid or expired token."
                    )
                # For non-auth JSON-RPC errors, log and return empty dict
                print(f"API Error on '{method}': {error_msg}")
                return {}

            return result

        except VCOAuthError:
            raise
        except requests.exceptions.HTTPError as e:
            print(f"API Error: {e}")
            return {}
        except Exception as e:
            print(f"API Error: {e}")
            return {}

    print(f"API Error: max retries exceeded for {method}")
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


def get_edge_link_series(enterprise_id: int, edge_id: int, start_ms: int, end_ms: int) -> dict:
    """Fetch per-edge link bandwidth time-series data from VCO.

    Calls the metrics/getEdgeLinkSeries JSON-RPC method to retrieve
    bytesTx and bytesRx samples for all links on a given edge within
    the specified time interval.

    Args:
        enterprise_id: The VCO enterprise ID that owns the edge.
        edge_id: The numeric edge ID (the ``id`` field, not ``logicalId``).
        start_ms: Interval start timestamp in UTC milliseconds since epoch.
        end_ms: Interval end timestamp in UTC milliseconds since epoch.

    Returns:
        The full parsed JSON-RPC response dict. The link series data is at
        response["result"]. Returns an empty dict on API error.
    """
    method = "metrics/getEdgeLinkSeries"
    params = {
        "enterpriseId": enterprise_id,
        "edgeId": edge_id,
        "interval": {"start": start_ms, "end": end_ms},
        "metrics": ["bytesTx", "bytesRx"],
    }
    return api_call(method, params)


def normalize_token(raw_token: str) -> str:
    """Normalize the VCO API token to ensure it has the required 'Token ' prefix.

    Args:
        raw_token: The token string from the environment variable. May or may
            not include the 'Token ' prefix.

    Returns:
        The token string with 'Token ' prefix guaranteed.
    """
    if not raw_token:
        raise ValueError("raw_token must be a non-empty string")
    if raw_token.startswith("Token "):
        return raw_token
    return f"Token {raw_token}"


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser for VCO edge export.

    Returns:
        argparse.ArgumentParser: Configured parser with --collect_95th and --months flags.
    """
    parser = argparse.ArgumentParser(
        description="Export VCO edge and license data, with optional 95th percentile bandwidth metrics."
    )
    parser.add_argument(
        "--collect_95th",
        action="store_true",
        default=False,
        help="Enable 95th percentile bandwidth metrics collection per edge link.",
    )
    parser.add_argument(
        "--months",
        type=int,
        default=1,
        help="Number of complete months to collect for 95th percentile metrics (used with --collect_95th).",
    )
    return parser


if __name__ == "__main__":

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    args = build_parser().parse_args()

    # Validate .env variables
    if not token:

        print("ERROR: VCO_TOKEN not found in .env")
        exit(1)

    if not vco_url:

        print("ERROR: VCO_URL not found in .env")
        exit(1)

    token = normalize_token(token)
    print(
        f"Token format: "
        f"{'provided with prefix' if os.getenv('VCO_TOKEN').startswith('Token ') else 'bare token, prefix auto-added'}"
    )

    if args.months < 1 or args.months > 12:
        logging.error("--months must be between 1 and 12, got %d", args.months)
        exit(1)

    if args.collect_95th:
        logging.info("95th percentile collection enabled for %d month(s).", args.months)
    else:
        logging.info("95th percentile collection disabled — standard edge export mode.")

    try:
        enterprise_ids = get_enterprise_ids()
    except VCOAuthError as e:
        print(f"ERROR: {e}")
        exit(1)

    if not enterprise_ids:
        print(
            "ERROR: No enterprises returned from VCO. "
            "This usually means the API token is invalid, expired, "
            "or lacks permissions. Verify VCO_TOKEN in .env."
        )
        exit(1)

    print(f"Found {len(enterprise_ids)} enterprises")

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
        exit(0)

    if (
        "Customer Name" not in license_df.columns
        or "Edge Name" not in license_df.columns
    ):
        print(
            f"ERROR: License CSV missing required column(s) for merge. "
            f"Available: {list(license_df.columns)}"
        )
        exit(1)

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
            if args.collect_95th:
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

    merged_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(
        f"Done. {len(merged_df)} rows written to '{OUTPUT_CSV}' "
        f"({matched_count} matched, {unmatched_count} unmatched)"
    )

    if args.collect_95th:
        target_months = get_target_months(args.months)
        print(
            f"\nCollecting 95th percentile metrics for {len(target_months)} month(s): "
            f"{', '.join(m['label'] for m in target_months)}"
        )
        metrics_results = []
        for edge_info in edge_info_list:
            print(
                f"\n  Processing edge: {edge_info['edge_name']} "
                f"({edge_info['enterprise_name']})"
            )
            for month in target_months:
                try:
                    response = get_edge_link_series(
                        edge_info["enterprise_id"],
                        edge_info["edge_id"],
                        month["start_ms"],
                        month["end_ms"],
                    )
                    link_series = response.get("result") or []
                    metrics = compute_edge_month_metrics(link_series, month["start_ms"])
                    metrics_results.append(
                        {
                            "enterprise_name": edge_info["enterprise_name"],
                            "edge_name": edge_info["edge_name"],
                            "month_label": month["label"],
                            **metrics,
                        }
                    )
                    print(
                        f"    {month['label']}: "
                        f"tx={metrics['monthly_tx_95th_mbps']:.4f} "
                        f"rx={metrics['monthly_rx_95th_mbps']:.4f} "
                        f"total={metrics['monthly_total_95th_mbps']:.4f} Mbps"
                    )
                except VCOAuthError:
                    raise  # Auth failures should still terminate
                except Exception as e:
                    logging.warning(
                        "Failed to collect metrics for edge %s (%s) month %s: %s",
                        edge_info["edge_name"],
                        edge_info["enterprise_name"],
                        month["label"],
                        e,
                    )
        print(
            f"\n95th percentile collection complete: "
            f"{len(metrics_results)} edge-month records computed"
        )
