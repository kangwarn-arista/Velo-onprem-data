"""Compare Maestro license export CSV against VCO edge export CSV.

Joins on Edge UUID (Maestro: 'Edge Logical ID', VCO: 'Edge UUID') and
compares serial number, edge name, model, license, status, and bandwidth.
Filters by enterprise name to scope the comparison.

Usage:
    uv run python compare_exports.py <maestro_csv> <vco_csv> <enterprise_name>

Example:
    uv run python compare_exports.py maestro-vcoEdgeInternal-08-08-2026.csv \
        vco116-usca1.velocloud.net.07-2026.csv "FIS"
"""

import argparse
import sys
from pathlib import Path

import pandas as pd


FIELD_MAP = [
    # (label, maestro_col, vco_col, case_insensitive)
    ("Serial Number", "Serial Number", "Edge Serial Number", False),
    ("Edge Name", "Name", "Edge Name", False),
    ("Edge Status", "Edge Status", "Edge Status", True),
    ("Model Number", "Model Number", "Model Number", True),
    ("License SKU", "License", "Edge License SKU", False),
]

BW_TOLERANCE_MBPS = 5.0


def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding_errors="replace")


def dedup_vco_latest_month(vco: pd.DataFrame) -> pd.DataFrame:
    """Keep only the latest Month-Year row per Edge UUID."""
    if "Month-Year" not in vco.columns or "Edge UUID" not in vco.columns:
        return vco
    vco = vco.copy()
    vco["_month_sort"] = pd.to_datetime(vco["Month-Year"], format="%m-%Y", errors="coerce")
    vco = vco.sort_values("_month_sort", ascending=False).drop_duplicates(subset="Edge UUID", keep="first")
    return vco.drop(columns=["_month_sort"])


def filter_by_enterprise(
    maestro: pd.DataFrame, vco: pd.DataFrame, enterprise: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Filter both DataFrames to rows matching the enterprise name (case-insensitive substring)."""
    ent_lower = enterprise.lower()

    maestro_col = "VCO Enterprise Name"
    m_mask = maestro[maestro_col].fillna("").str.lower().str.contains(ent_lower)
    m_filtered = maestro[m_mask].copy()

    vco_col = "Customer Name"
    v_mask = vco[vco_col].fillna("").str.lower().str.contains(ent_lower)
    v_filtered = vco[v_mask].copy()

    return m_filtered, v_filtered


def _resolve_col(df: pd.DataFrame, col: str, suffix: str) -> str | None:
    """Return the suffixed column name if it exists, else the bare name, else None."""
    suffixed = f"{col}{suffix}"
    if suffixed in df.columns:
        return suffixed
    if col in df.columns:
        return col
    return None


def compare(maestro: pd.DataFrame, vco: pd.DataFrame) -> dict:
    """Join on UUID and compare field by field."""
    merged = maestro.merge(
        vco,
        left_on="Edge Logical ID",
        right_on="Edge UUID",
        how="outer",
        suffixes=("_maestro", "_vco"),
        indicator=True,
    )

    results = {
        "maestro_only": merged[merged["_merge"] == "left_only"],
        "vco_only": merged[merged["_merge"] == "right_only"],
        "matched": merged[merged["_merge"] == "both"],
        "mismatches": [],
        "bw_diffs": pd.DataFrame(),
    }

    matched = results["matched"]

    for label, m_col, v_col, case_insensitive in FIELD_MAP:
        mc = _resolve_col(matched, m_col, "_maestro")
        vc = _resolve_col(matched, v_col, "_vco")
        if mc is None or vc is None:
            continue

        m_vals = matched[mc].fillna("").astype(str).str.strip()
        v_vals = matched[vc].fillna("").astype(str).str.strip()
        if case_insensitive:
            mask = m_vals.str.lower() != v_vals.str.lower()
        else:
            mask = m_vals != v_vals

        if mask.any():
            diffs = matched[mask][["Edge Logical ID", mc, vc]].copy()
            diffs.columns = ["Edge UUID", f"Maestro {label}", f"VCO {label}"]
            results["mismatches"].append((label, diffs))

    # Bandwidth: numeric comparison with tolerance
    m_bw_col = _resolve_col(matched, "30 Days 95th", "_maestro")
    v_bw_col = _resolve_col(matched, "monthly_total_95th_mbps", "_vco")
    if m_bw_col and v_bw_col:
        m_bw = pd.to_numeric(matched[m_bw_col], errors="coerce")
        v_bw = pd.to_numeric(matched[v_bw_col], errors="coerce")
        bw_mask = (m_bw - v_bw).abs() > BW_TOLERANCE_MBPS
        both_valid = m_bw.notna() & v_bw.notna()
        bw_mask = bw_mask & both_valid
        if bw_mask.any():
            name_col = _resolve_col(matched, "Name", "_maestro") or "Edge Logical ID"
            bw_diffs = matched[bw_mask][["Edge Logical ID", name_col]].copy()
            bw_diffs["Maestro 95th"] = m_bw[bw_mask].values
            bw_diffs["VCO 95th"] = v_bw[bw_mask].round(1).values
            bw_diffs["Delta"] = (m_bw[bw_mask] - v_bw[bw_mask]).round(1).values
            bw_diffs.columns = ["Edge UUID", "Edge Name", "Maestro 95th", "VCO 95th", "Delta (Mbps)"]
            results["bw_diffs"] = bw_diffs

    return results


def print_report(results: dict, enterprise: str) -> int:
    matched = results["matched"]
    maestro_only = results["maestro_only"]
    vco_only = results["vco_only"]
    mismatches = results["mismatches"]

    print(f"\n{'=' * 70}")
    print(f"  CSV Comparison Report — Enterprise: {enterprise}")
    print(f"{'=' * 70}")
    print(f"  Matched edges (both files):  {len(matched)}")
    print(f"  Maestro-only edges:          {len(maestro_only)}")
    print(f"  VCO-only edges:              {len(vco_only)}")
    print(f"{'=' * 70}")

    issue_count = 0

    if not maestro_only.empty:
        print(f"\n--- Edges in Maestro but NOT in VCO export ({len(maestro_only)}) ---")
        cols = ["Serial Number", "Name", "Edge Logical ID"]
        available = [c for c in cols if c in maestro_only.columns]
        print(maestro_only[available].to_string(index=False))
        issue_count += len(maestro_only)

    if not vco_only.empty:
        print(f"\n--- Edges in VCO export but NOT in Maestro ({len(vco_only)}) ---")
        cols = ["Edge Serial Number", "Edge Name", "Edge UUID"]
        available = [c for c in cols if c in vco_only.columns]
        print(vco_only[available].to_string(index=False))
        issue_count += len(vco_only)

    if mismatches:
        print(f"\n--- Field Mismatches (matched edges) ---")
        for label, diffs in mismatches:
            print(f"\n  [{label}] — {len(diffs)} difference(s)")
            print(diffs.to_string(index=False))
            issue_count += len(diffs)

    bw_diffs = results["bw_diffs"]
    if not bw_diffs.empty:
        print(f"\n--- Bandwidth 95th Percentile Differences > {BW_TOLERANCE_MBPS} Mbps ({len(bw_diffs)}) ---")
        print(bw_diffs.to_string(index=False))
        issue_count += len(bw_diffs)

    if issue_count == 0:
        print("\n  All edges matched with no field differences.")

    print(f"\n{'=' * 70}")
    print(f"  Total issues: {issue_count}")
    print(f"{'=' * 70}\n")
    return issue_count


def main():
    parser = argparse.ArgumentParser(
        description="Compare Maestro license CSV against VCO edge export CSV"
    )
    parser.add_argument("maestro_csv", type=Path, help="Maestro license export CSV")
    parser.add_argument("vco_csv", type=Path, help="VCO edge export CSV")
    parser.add_argument("enterprise", help="Enterprise name to filter (substring match)")
    args = parser.parse_args()

    for p in [args.maestro_csv, args.vco_csv]:
        if not p.exists():
            print(f"ERROR: File not found: {p}", file=sys.stderr)
            sys.exit(1)

    maestro = load_csv(args.maestro_csv)
    vco = load_csv(args.vco_csv)

    m_filtered, v_filtered = filter_by_enterprise(maestro, vco, args.enterprise)
    v_filtered = dedup_vco_latest_month(v_filtered)
    print(f"Filtered: {len(m_filtered)} Maestro rows, {len(v_filtered)} VCO rows (deduped to latest month) for '{args.enterprise}'")

    if m_filtered.empty and v_filtered.empty:
        print(f"No rows found for enterprise '{args.enterprise}' in either file.")
        sys.exit(0)

    results = compare(m_filtered, v_filtered)
    issue_count = print_report(results, args.enterprise)
    sys.exit(1 if issue_count > 0 else 0)


if __name__ == "__main__":
    main()
