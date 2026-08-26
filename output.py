"""CSV generation and zip packaging for VCO 95th percentile metrics output.

Provides pure functions for extracting the VCO hostname from a URL,
writing per-month CSV files enriched with 95th percentile bandwidth
metrics columns, and packaging a directory of CSVs into a zip archive.
No VCO API credentials are required -- all functions operate on local
data structures and the filesystem.
"""
import io
import json
import math
import zipfile
from pathlib import Path
from urllib.parse import urlparse


import pandas as pd


def build_output_metadata(
    version: str,
    vco_host: str,
    generated_at: str,
    *,
    vco_version: str | None = None,
    vco_build: str | None = None,
) -> dict:
    """Build a sanitized metadata dict for the output archive.

    Returns only non-sensitive identification fields. Intentionally excludes
    collection parameters (months, edge count, record count, collection mode,
    all_metrics flag, enterprise count) to prevent information disclosure in
    the ``_metadata.json`` file embedded in output archives.

    Args:
        version: Application version string.
        vco_host: VCO hostname used for the export.
        generated_at: Timestamp string for when the export was generated.
        vco_version: Optional VCO software version (e.g. ``"6.4.2.5"``).
        vco_build: Optional VCO build identifier
            (e.g. ``"R6135-20260803-0930-GA-9af6dfb8fe"``).

    Returns:
        Dict with identification keys: ``version``, ``vco_host``,
        ``generated_at``, and optionally ``vco_version`` / ``vco_build``.
    """
    result = {
        "version": version,
        "vco_host": vco_host,
        "generated_at": generated_at,
    }
    if vco_version is not None:
        result["vco_version"] = vco_version
    if vco_build is not None:
        result["vco_build"] = vco_build
    return result


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

_PEAK_METRIC_COL = "monthly_peak_95th_mbps"

_COLUMN_RENAME = {
    "monthly_total_95th_mbps": "30 Days 95th",
    "monthly_tx_95th_mbps": "30 Days Tx 95th",
    "monthly_rx_95th_mbps": "30 Days Rx 95th",
    _PEAK_METRIC_COL: "30 Days P95 Peak",
}


def write_month_csvs(
    merged_df: pd.DataFrame,
    metrics_results: list[dict],
    target_months: list[dict],
    vco_name: str,
    output_dir: str,
    *,
    all_metrics: bool = False,
    include_peak: bool = False,
) -> list[str]:
    """Write one CSV file per target month enriched with 95th percentile metrics.

    For each month in ``target_months``, creates a copy of ``merged_df`` with
    a ``Month-Year`` column and left-merged p95 metrics columns.  Edges that
    have no metrics entry for a given month will have ``NaN`` in the p95
    columns.

    By default only the total 95th percentile column (``30 Days 95th``) is
    included.  When ``all_metrics`` is ``True``, the tx and rx columns are
    also included.

    The ``30 Days P95 Peak`` column is always present in the output.  When
    ``include_peak`` is ``True`` the column contains computed peak P95
    values from the metrics data.  When ``False`` (VCO < 6.4) the column
    is empty.

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
        include_peak: When ``True``, include peak P95 data from metrics
            results.  When ``False``, the column appears but is empty.

    Returns:
        List of absolute file paths (as strings) for every CSV written, in
        the same order as ``target_months``.
    """
    metric_cols = _ALL_METRIC_COLS if all_metrics else ["monthly_total_95th_mbps"]
    if include_peak:
        metric_cols = metric_cols + [_PEAK_METRIC_COL]

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

        if _PEAK_METRIC_COL not in month_df.columns:
            month_df[_PEAK_METRIC_COL] = float("nan")

        rename_map = {k: v for k, v in _COLUMN_RENAME.items() if k in month_df.columns}
        month_df.rename(columns=rename_map, inplace=True)

        filename = f"{vco_name}.{month_label}.csv"
        full_path = str(Path(output_dir) / filename)
        month_df.to_csv(full_path, index=False, encoding="utf-8-sig")
        csv_paths.append(full_path)

    return csv_paths


def write_combined_csv(
    merged_df: pd.DataFrame,
    metrics_results: list[dict],
    target_months: list[dict],
    vco_name: str,
    output_dir: str,
    *,
    include_peak: bool = False,
) -> str:
    """Write a single CSV file with one row per edge and a Record Hash column.

    Produces a combined CSV named ``{vco_name}.combined.csv`` where metric
    columns are replaced by an obfuscated Record Hash computed by
    :func:`encoder.encode_record_hash`.  The Record Hash encodes per-month
    95th percentile bandwidth metrics into a fixed-length 344-character
    base64 string.  Edges with an empty or missing UUID receive the
    ``SENTINEL_HASH`` value.

    The output CSV retains all columns from ``merged_df`` and adds a
    ``"Record Hash"`` column.  The per-month metric columns (``Month-Year``,
    ``30 Days 95th``, ``30 Days P95 Peak``) are NOT included — the Record
    Hash is the sole summary of metric data per edge.

    CSV files are written with UTF-8 BOM encoding (``utf-8-sig``), matching
    the convention used by :func:`write_month_csvs`.

    Args:
        merged_df: DataFrame containing the merged license and edge status
            data.  Must include at least ``"Customer Name"``,
            ``"Edge Name"``, and ``"Edge UUID"`` columns.
        metrics_results: List of dicts, each with keys ``enterprise_name``,
            ``edge_name``, ``month_label``, ``monthly_total_95th_mbps``,
            and optionally ``monthly_peak_95th_mbps``.
        target_months: List of month dicts, each with a ``"label"`` key
            (format ``"MM-YYYY"`` or ``"last30d"``).
        vco_name: VCO hostname string used as the CSV filename prefix.
        output_dir: Directory path where the CSV file will be written.
        include_peak: When ``True``, encode peak P95 data into the Record
            Hash.  When ``False``, the peak slot uses NaN (encoded as
            ``-1.0`` sentinel).

    Returns:
        Absolute file path (as string) for the written CSV file.
    """
    # Deferred import — same pattern as create_encrypted_archive importing from crypto
    from encoder import encode_record_hash

    # Build O(1) metrics lookup: (Customer Name, Edge Name, month_label) → record
    metrics_lookup: dict[tuple[str, str, str], dict] = {}
    for record in metrics_results:
        key = (record["enterprise_name"], record["edge_name"], record["month_label"])
        metrics_lookup[key] = record

    result_df = merged_df.copy()
    record_hashes: list[str] = []

    for _, row in result_df.iterrows():
        customer_name = row["Customer Name"]
        edge_name = row["Edge Name"]
        raw_uuid = row.get("Edge UUID", "")
        edge_uuid = "" if (raw_uuid is None or (isinstance(raw_uuid, float) and math.isnan(raw_uuid))) else str(raw_uuid)

        months_data: list[dict] = []
        for month in target_months:
            month_label = month["label"]
            record = metrics_lookup.get((customer_name, edge_name, month_label))
            if record is not None:
                p95 = record.get("monthly_total_95th_mbps", float("nan"))
                peak = (
                    record.get("monthly_peak_95th_mbps", float("nan"))
                    if include_peak
                    else float("nan")
                )
            else:
                p95 = float("nan")
                peak = float("nan")
            months_data.append({"label": month_label, "95th": p95, "peak": peak})

        record_hashes.append(encode_record_hash(months_data, edge_uuid))

    result_df["Record Hash"] = record_hashes

    filename = f"{vco_name}.combined.csv"
    full_path = str(Path(output_dir) / filename)
    result_df.to_csv(full_path, index=False, encoding="utf-8-sig")
    return full_path


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


def create_encrypted_archive(
    source_dir: str,
    zip_path: str,
    *,
    metadata: dict | None = None,
) -> str:
    """Compress-then-encrypt CSV files into a two-file archive.

    Collects all files in ``source_dir`` into an in-memory zip, encrypts the
    resulting bytes with Fernet, then writes a final zip containing
    ``data.enc`` (the encrypted blob) and ``_metadata.json`` (if provided).

    Args:
        source_dir: Path to the directory containing files to archive.
        zip_path: Destination path for the output zip file.
        metadata: Optional dict written as ``_metadata.json`` inside the
            archive.

    Returns:
        The ``zip_path`` string that was passed in.
    """
    from crypto import encrypt_blob

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as inner_zf:
        for file in Path(source_dir).iterdir():
            if file.is_file():
                inner_zf.write(file, arcname=file.name)

    encrypted_blob = encrypt_blob(buffer.getvalue())

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("data.enc", encrypted_blob)
        if metadata is not None:
            zf.writestr("_metadata.json", json.dumps(metadata, indent=2))

    return zip_path
