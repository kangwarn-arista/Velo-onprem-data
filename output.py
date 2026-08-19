"""CSV generation and zip packaging for VCO 95th percentile metrics output.

Provides pure functions for extracting the VCO hostname from a URL,
writing per-month CSV files enriched with 95th percentile bandwidth
metrics columns, and packaging a directory of CSVs into a zip archive.
No VCO API credentials are required -- all functions operate on local
data structures and the filesystem.
"""
import json
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
    if not parsed.hostname:
        raise ValueError(
            f"Cannot extract hostname from VCO URL {vco_url!r}. "
            "Ensure VCO_URL includes a scheme (e.g. 'https://vco.example.com/portal/')."
        )
    return parsed.hostname


_ALL_METRIC_COLS = [
    "monthly_tx_95th_mbps",
    "monthly_rx_95th_mbps",
    "monthly_total_95th_mbps",
]

_COLUMN_RENAME = {
    "monthly_total_95th_mbps": "30 Days 95th",
    "monthly_tx_95th_mbps": "30 Days Tx 95th",
    "monthly_rx_95th_mbps": "30 Days Rx 95th",
}


def write_month_csvs(
    merged_df: pd.DataFrame,
    metrics_results: list[dict],
    target_months: list[dict],
    vco_name: str,
    output_dir: str,
    *,
    all_metrics: bool = False,
) -> list[str]:
    """Write one CSV file per target month enriched with 95th percentile metrics.

    For each month in ``target_months``, creates a copy of ``merged_df`` with
    a ``Month-Year`` column and left-merged p95 metrics columns.  Edges that
    have no metrics entry for a given month will have ``NaN`` in the p95
    columns.

    By default only the total 95th percentile column (``30 Days 95th``) is
    included.  When ``all_metrics`` is ``True``, the tx and rx columns are
    also included.

    CSV files are written with UTF-8 BOM encoding (``utf-8-sig``) and named
    using the pattern ``{vco_name}.{MM-YYYY}.csv``.

    Args:
        merged_df: DataFrame containing the merged license and edge status
            data.  Must include at least ``"Customer Name"`` and
            ``"Edge Name"`` columns.
        metrics_results: List of dicts, each with keys ``enterprise_name``,
            ``edge_name``, ``month_label``, and
            ``monthly_{tx,rx,total}_95th_mbps``.
        target_months: List of month dicts as returned by
            :func:`metrics.get_target_months`, each with a ``"label"`` key
            (format ``"MM-YYYY"``).
        vco_name: VCO hostname string used as the CSV filename prefix.
        output_dir: Directory path where the CSV files will be written.
        all_metrics: When ``True``, include tx and rx columns alongside
            total.  Defaults to ``False`` (total only).

    Returns:
        List of absolute file paths (as strings) for every CSV written, in
        the same order as ``target_months``.
    """
    metric_cols = _ALL_METRIC_COLS if all_metrics else ["monthly_total_95th_mbps"]

    csv_paths: list[str] = []

    for month in target_months:
        month_label: str = month["label"]

        month_metrics = [
            r for r in metrics_results if r.get("month_label") == month_label
        ]

        month_df = merged_df.copy()
        month_df["Month-Year"] = month_label

        if month_metrics:
            metrics_df = pd.DataFrame(month_metrics).rename(
                columns={
                    "enterprise_name": "Customer Name",
                    "edge_name": "Edge Name",
                }
            )[["Customer Name", "Edge Name"] + metric_cols]
            month_df = month_df.merge(
                metrics_df, on=["Customer Name", "Edge Name"], how="left"
            )
        else:
            for col in metric_cols:
                month_df[col] = float("nan")

        rename_map = {k: v for k, v in _COLUMN_RENAME.items() if k in month_df.columns}
        month_df.rename(columns=rename_map, inplace=True)

        filename = f"{vco_name}.{month_label}.csv"
        full_path = str(Path(output_dir) / filename)
        month_df.to_csv(full_path, index=False, encoding="utf-8-sig")
        csv_paths.append(full_path)

    return csv_paths


def create_zip_archive(
    source_dir: str,
    zip_path: str,
    *,
    metadata: dict | None = None,
) -> str:
    """Package all files in a directory into a single zip archive.

    Iterates over all entries in ``source_dir`` using
    :func:`pathlib.Path.iterdir` and adds each file to the archive using
    only the file's basename as the archive member name, so no directory
    path information is included in the zip.

    Args:
        source_dir: Path to the directory containing files to archive.
        zip_path: Destination path for the zip file to create.
        metadata: Optional dict written as ``_metadata.json`` inside the
            archive (version, host, generation timestamp, etc.).

    Returns:
        The ``zip_path`` string that was passed in.
    """
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in Path(source_dir).iterdir():
            if file.is_file():
                zf.write(file, arcname=file.name)
        if metadata is not None:
            zf.writestr(
                "_metadata.json",
                json.dumps(metadata, indent=2),
            )

    return zip_path
