"""Pure computation functions for VCO bandwidth metrics.

Provides month range calculation, bytes-to-Mbps conversion,
95th percentile computation, cross-link sample aggregation,
and the full edge-month metrics pipeline.  Uses only Python
stdlib -- no third-party dependencies.
"""
import math
from collections import defaultdict
from datetime import date, datetime, timezone


def get_target_months(
    num_months: int, reference_date: date | None = None
) -> list[dict]:
    """Return the last N complete calendar months before the reference date.

    Walks backward from the month immediately before ``reference_date``,
    collecting ``num_months`` entries.  The current partial month is never
    included, even when ``reference_date`` falls on the 1st.

    Args:
        num_months: How many complete months to return.
        reference_date: Anchor date.  Defaults to ``date.today()`` when
            ``None``.

    Returns:
        List of dicts (oldest first) with keys ``year``, ``month``,
        ``start_ms``, ``end_ms``, and ``label``.  Timestamps are UTC
        milliseconds since epoch.
    """
    if num_months < 1:
        raise ValueError(f"num_months must be >= 1, got {num_months}")

    if reference_date is None:
        reference_date = date.today()

    months: list[dict] = []
    year = reference_date.year
    month = reference_date.month

    for _ in range(num_months):
        # Step back one month
        month -= 1
        if month < 1:
            month = 12
            year -= 1

        start_dt = datetime(year, month, 1, tzinfo=timezone.utc)
        start_ms = int(start_dt.timestamp() * 1000)

        # Compute start of the next month for end_ms
        next_month = month + 1
        next_year = year
        if next_month > 12:
            next_month = 1
            next_year = year + 1
        end_dt = datetime(next_year, next_month, 1, tzinfo=timezone.utc)
        end_ms = int(end_dt.timestamp() * 1000)

        months.append(
            {
                "year": year,
                "month": month,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "label": f"{month:02d}-{year}",
            }
        )

    months.reverse()
    return months


def bytes_to_mbps(byte_count: int | float) -> float:
    """Convert a 5-minute byte count to megabits per second.

    Uses the formula: ``bytes * 8 / 1_048_576 / 300``.

    Args:
        byte_count: Total bytes transferred in one 5-minute sample interval.

    Returns:
        Throughput in megabits per second (Mbps).
    """
    return byte_count * 8 / 1_048_576 / 300


def percentile_95(values: list[float | int]) -> float | int:
    """Compute the 95th percentile using the ceiling-rank method.

    Sorts the values and picks the element at position
    ``ceil(count * 0.95)`` (1-indexed).

    Args:
        values: Non-empty list of numeric values.

    Raises:
        ValueError: If ``values`` is empty.

    Returns:
        The value at the 95th percentile position.
    """
    if not values:
        raise ValueError("Cannot compute percentile of empty list")
    sorted_vals = sorted(values)
    position = math.ceil(len(sorted_vals) * 0.95)
    return sorted_vals[position - 1]


def aggregate_link_samples(link_series_result: list[dict]) -> list[dict]:
    """Sum bytesTx and bytesRx across all links at each 5-minute sample index.

    Each element in ``link_series_result`` represents one link and is
    expected to have a ``"series"`` key containing a list of sample dicts
    with ``"bytesTx"`` and ``"bytesRx"`` keys.

    Args:
        link_series_result: List of link dicts, each with a ``"series"``
            key mapping to a list of per-sample dicts.

    Returns:
        List of dicts with keys ``tx_bytes`` and ``rx_bytes``, one per
        sample index.  Returns an empty list when no series data exists.
    """
    all_series = [link.get("series") or [] for link in link_series_result]
    if not all_series:
        return []

    max_length = max((len(s) for s in all_series), default=0)
    if max_length == 0:
        return []

    aggregated: list[dict] = []
    for i in range(max_length):
        tx_total = 0
        rx_total = 0
        for series in all_series:
            if i < len(series):
                tx_total += series[i].get("bytesTx", 0)
                rx_total += series[i].get("bytesRx", 0)
        aggregated.append({"tx_bytes": tx_total, "rx_bytes": rx_total})

    return aggregated


def compute_edge_month_metrics(
    link_series_result: list[dict], start_ms: int
) -> dict:
    """Compute monthly 95th percentile bandwidth metrics for one edge.

    Runs the full pipeline: aggregate link samples, convert bytes to Mbps,
    group by UTC day, compute daily 95th percentiles, then compute the
    monthly 95th percentile from the daily values.

    Args:
        link_series_result: List of link dicts as returned by the VCO
            ``metrics/getEdgeLinkSeries`` API.
        start_ms: Start timestamp of the month in UTC milliseconds since
            epoch.  Used to assign each sample to a calendar day.

    Returns:
        Dict with 9 keys: ``monthly_{tx,rx,total}_{95th,max,avg}_mbps``.
        All values are 0.0 when no sample data is available.
    """
    zero_result = {
        "monthly_tx_95th_mbps": 0.0,
        "monthly_rx_95th_mbps": 0.0,
        "monthly_total_95th_mbps": 0.0,
        "monthly_tx_max_mbps": 0.0,
        "monthly_rx_max_mbps": 0.0,
        "monthly_total_max_mbps": 0.0,
        "monthly_tx_avg_mbps": 0.0,
        "monthly_rx_avg_mbps": 0.0,
        "monthly_total_avg_mbps": 0.0,
    }

    samples = aggregate_link_samples(link_series_result)
    if not samples:
        return zero_result

    # Group samples by UTC day
    daily_buckets: dict[date, dict[str, list[float]]] = defaultdict(
        lambda: {"tx": [], "rx": [], "total": []}
    )

    for i, sample in enumerate(samples):
        tx_bytes = sample["tx_bytes"]
        rx_bytes = sample["rx_bytes"]

        tx_mbps = bytes_to_mbps(tx_bytes)
        rx_mbps = bytes_to_mbps(rx_bytes)
        total_mbps = bytes_to_mbps(tx_bytes + rx_bytes)

        sample_ts_ms = start_ms + i * 300_000
        sample_date = datetime.fromtimestamp(
            sample_ts_ms / 1000, tz=timezone.utc
        ).date()

        daily_buckets[sample_date]["tx"].append(tx_mbps)
        daily_buckets[sample_date]["rx"].append(rx_mbps)
        daily_buckets[sample_date]["total"].append(total_mbps)

    # Compute daily p95 values
    all_daily_tx: list[float] = []
    all_daily_rx: list[float] = []
    all_daily_total: list[float] = []

    for day_data in daily_buckets.values():
        all_daily_tx.append(percentile_95(day_data["tx"]))
        all_daily_rx.append(percentile_95(day_data["rx"]))
        all_daily_total.append(percentile_95(day_data["total"]))

    return {
        "monthly_tx_95th_mbps": percentile_95(all_daily_tx),
        "monthly_rx_95th_mbps": percentile_95(all_daily_rx),
        "monthly_total_95th_mbps": percentile_95(all_daily_total),
        "monthly_tx_max_mbps": max(all_daily_tx),
        "monthly_rx_max_mbps": max(all_daily_rx),
        "monthly_total_max_mbps": max(all_daily_total),
        "monthly_tx_avg_mbps": sum(all_daily_tx) / len(all_daily_tx),
        "monthly_rx_avg_mbps": sum(all_daily_rx) / len(all_daily_rx),
        "monthly_total_avg_mbps": sum(all_daily_total) / len(all_daily_total),
    }
