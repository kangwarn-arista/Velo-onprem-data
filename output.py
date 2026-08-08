"""CSV generation and zip packaging for VCO 95th percentile metrics output.

Provides pure functions for extracting the VCO hostname from a URL,
writing per-month CSV files enriched with 95th percentile bandwidth
metrics columns, and packaging a directory of CSVs into a zip archive.
No VCO API credentials are required -- all functions operate on local
data structures and the filesystem.
"""
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd


def extract_vco_name(vco_url: str) -> str:
    """Extract the VCO hostname from a VCO URL for use in output filenames.

    Uses :func:`urllib.parse.urlparse` to parse the URL, which automatically
    strips the port, scheme, path, and query components and returns only the
    network location hostname.

    Args:
        vco_url: Full VCO URL, e.g. ``"https://vco.example.com/portal/"``
            or ``"https://vco.example.com:8443/portal/"``.

    Returns:
        Hostname string without port, protocol, or path, e.g.
        ``"vco.example.com"``.
    """
    parsed = urlparse(vco_url)
    return parsed.hostname


def write_month_csvs(
    merged_df: pd.DataFrame,
    metrics_results: list[dict],
    target_months: list[dict],
    vco_name: str,
    output_dir: str,
) -> list[str]:
    """Write one CSV file per target month enriched with 95th percentile metrics.

    For each month in ``target_months``, creates a copy of ``merged_df`` with
    a ``Month-Year`` column and left-merged p95 metrics columns.  Edges that
    have no metrics entry for a given month will have ``NaN`` in the three p95
    columns.

    CSV files are written with UTF-8 BOM encoding (``utf-8-sig``) and named
    using the pattern ``{vco_name}.{MM-YYYY}.csv``.

    Args:
        merged_df: DataFrame containing the merged license and edge status
            data.  Must include at least ``"Customer Name"`` and
            ``"Edge Name"`` columns.
        metrics_results: List of dicts, each with keys ``enterprise_name``,
            ``edge_name``, ``month_label``, ``monthly_tx_95th_mbps``,
            ``monthly_rx_95th_mbps``, and ``monthly_total_95th_mbps``.
        target_months: List of month dicts as returned by
            :func:`metrics.get_target_months`, each with a ``"label"`` key
            (format ``"MM-YYYY"``).
        vco_name: VCO hostname string used as the CSV filename prefix.
        output_dir: Directory path where the CSV files will be written.

    Returns:
        List of absolute file paths (as strings) for every CSV written, in
        the same order as ``target_months``.
    """
    csv_paths: list[str] = []

    for month in target_months:
        month_label: str = month["label"]

        # Filter metrics to this month only
        month_metrics = [
            r for r in metrics_results if r.get("month_label") == month_label
        ]

        # Copy merged_df and tag every row with the month label
        month_df = merged_df.copy()
        month_df["Month-Year"] = month_label

        if month_metrics:
            metrics_df = pd.DataFrame(month_metrics).rename(
                columns={
                    "enterprise_name": "Customer Name",
                    "edge_name": "Edge Name",
                }
            )[
                [
                    "Customer Name",
                    "Edge Name",
                    "monthly_tx_95th_mbps",
                    "monthly_rx_95th_mbps",
                    "monthly_total_95th_mbps",
                ]
            ]
            month_df = month_df.merge(
                metrics_df, on=["Customer Name", "Edge Name"], how="left"
            )
        else:
            # No metrics at all for this month -- add NaN columns
            month_df["monthly_tx_95th_mbps"] = float("nan")
            month_df["monthly_rx_95th_mbps"] = float("nan")
            month_df["monthly_total_95th_mbps"] = float("nan")

        filename = f"{vco_name}.{month_label}.csv"
        full_path = str(Path(output_dir) / filename)
        month_df.to_csv(full_path, index=False, encoding="utf-8-sig")
        csv_paths.append(full_path)

    return csv_paths


def create_zip_archive(source_dir: str, zip_path: str) -> str:
    """Package all files in a directory into a single zip archive.

    Iterates over all entries in ``source_dir`` using
    :func:`pathlib.Path.iterdir` and adds each file to the archive using
    only the file's basename as the archive member name, so no directory
    path information is included in the zip.

    Args:
        source_dir: Path to the directory containing files to archive.
        zip_path: Destination path for the zip file to create.

    Returns:
        The ``zip_path`` string that was passed in.
    """
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in Path(source_dir).iterdir():
            zf.write(file, arcname=file.name)

    return zip_path
