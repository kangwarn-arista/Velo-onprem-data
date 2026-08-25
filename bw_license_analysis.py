#!/usr/bin/env python3
"""Analyze VCO edge export CSVs to recommend bandwidth license tiers based on 30-day 95th percentile usage."""

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

from pydantic import BaseModel

SKU_TIERS: list[tuple[str, int]] = [
    ("10M", 10),
    ("30M", 30),
    ("50M", 50),
    ("100M", 100),
    ("200M", 200),
    ("500M", 500),
    ("1G", 1_024),
    ("2G", 2_048),
    ("10G", 10_240),
    ("20G", 20_240),
    ("40G", 40_960),
    ("100G", 102_400),
]

TIER_ORDER: dict[str, int] = {sku: i for i, (sku, _) in enumerate(SKU_TIERS)}

RAW_BW_TO_DISPLAY: dict[str, str] = {
    "010M": "10M",
    "030M": "30M",
    "050M": "50M",
    "100M": "100M",
    "200M": "200M",
    "500M": "500M",
    "001G": "1G",
    "002G": "2G",
    "005G": "5G",
    "010G": "10G",
    "020G": "20G",
    "040G": "40G",
    "100G": "100G",
}


class EdgeRecord(BaseModel):
    edge_id: str
    edge_name: str
    current_bw_raw: str
    current_bw_display: str
    p95_mbps: float
    new_license: str


def determine_license_tier(p95_mbps: float) -> str:
    for sku, threshold in SKU_TIERS:
        if p95_mbps <= threshold:
            return sku
    return SKU_TIERS[-1][0]


def normalize_bandwidth(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return "UNASSIGNED"
    return RAW_BW_TO_DISPLAY.get(raw, raw)


def parse_csv(filepath: Path) -> list[EdgeRecord]:
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        seen_edges: dict[str, EdgeRecord] = {}

        for row in reader:
            edge_id = row["Edge Id"]
            is_active = row.get("Is License Active", "").strip()
            bw_raw = row.get("Bandwidth", "").strip()
            edge_status = row.get("Edge Status", "").strip()

            if edge_status == "OFFLINE":
                continue

            if edge_id in seen_edges:
                if is_active == "Yes" and bw_raw:
                    pass  # overwrite below
                else:
                    continue

            if is_active != "Yes" and bw_raw:
                continue

            p95_str = row.get("30 Days 95th", "0").strip()
            p95 = float(p95_str) if p95_str else 0.0

            seen_edges[edge_id] = EdgeRecord(
                edge_id=edge_id,
                edge_name=row["Edge Name"].strip(),
                current_bw_raw=bw_raw,
                current_bw_display=normalize_bandwidth(bw_raw),
                p95_mbps=p95,
                new_license=determine_license_tier(p95),
            )

    return sorted(seen_edges.values(), key=lambda e: (TIER_ORDER.get(e.new_license, len(SKU_TIERS)), e.edge_name))


def print_distribution(label: str, counter: Counter[str], max_bar_width: int = 40) -> None:
    total = sum(counter.values())
    sorted_items = sorted(counter.items(), key=lambda x: TIER_ORDER.get(x[0], len(SKU_TIERS)))
    print(f"\n  {label} ({total} edges):")
    for tier, count in sorted_items:
        pct = count / total * 100 if total else 0
        bar = "█" * round(pct / 100 * max_bar_width)
        print(f"    {tier:<12} {count:>4}  ({pct:5.1f}%)  {bar}")


def analyze_file(filepath: Path) -> list[EdgeRecord]:
    edges = parse_csv(filepath)
    filename = filepath.name

    print(f"\n{'=' * 80}")
    print(f"  File: {filename}")
    print(f"  Edges: {len(edges)}")
    print(f"{'=' * 80}")

    print(f"\n  {'Edge Name':<40} {'95th (Mbps)':>12} {'Current':>10} {'New':>10} {'Change':>8}")
    print(f"  {'-' * 40} {'-' * 12} {'-' * 10} {'-' * 10} {'-' * 8}")

    changed_count = 0
    for edge in edges:
        changed = edge.current_bw_display != edge.new_license
        marker = " *" if changed else ""
        if changed:
            changed_count += 1
        print(
            f"  {edge.edge_name:<40} {edge.p95_mbps:>12.1f} {edge.current_bw_display:>10} {edge.new_license:>10}{marker}"
        )

    print(f"\n  * = license change recommended ({changed_count} of {len(edges)} edges)")

    before = Counter(e.current_bw_display for e in edges)
    after = Counter(e.new_license for e in edges)
    print_distribution("BEFORE (current license)", before)
    print_distribution("AFTER  (based on 95th percentile)", after)

    return edges


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze VCO edge bandwidth licenses vs 95th percentile usage")
    parser.add_argument("csv_files", nargs="+", type=Path, help="One or more CSV export files to analyze")
    args = parser.parse_args()

    csv_only = [f for f in args.csv_files if f.suffix.lower() == ".csv"]
    if not csv_only:
        print("ERROR: No CSV files provided", file=sys.stderr)
        sys.exit(1)
    for f in csv_only:
        if not f.exists():
            print(f"ERROR: File not found: {f}", file=sys.stderr)
            sys.exit(1)

    print("VCO Edge Bandwidth License Analysis")
    print(f"SKU Tier Table: {', '.join(f'{s}={t} Mbps' for s, t in SKU_TIERS)}")

    all_edges: list[EdgeRecord] = []
    for csv_file in csv_only:
        all_edges.extend(analyze_file(csv_file))

    if len(csv_only) > 1:
        print(f"\n{'=' * 80}")
        print(f"  COMBINED SUMMARY ({len(csv_only)} files, {len(all_edges)} total edge records)")
        print(f"{'=' * 80}")
        before = Counter(e.current_bw_display for e in all_edges)
        after = Counter(e.new_license for e in all_edges)
        print_distribution("BEFORE (current license)", before)
        print_distribution("AFTER  (based on 95th percentile)", after)


if __name__ == "__main__":
    main()
