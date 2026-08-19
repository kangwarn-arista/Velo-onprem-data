"""Pure computation functions for VCO bandwidth metrics.

Provides month range calculation, bytes-to-Mbps conversion,
95th percentile computation, cross-link sample aggregation,
and the full edge-month metrics pipeline.  Uses only Python
stdlib -- no third-party dependencies.
"""
import calendar
import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

SAMPLES_PER_DAY = 288  # 12 samples/hr × 24 hrs (5-minute intervals)


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


def max_samples_for_month(year: int, month: int) -> int:
    """Return the expected number of 5-minute samples in a calendar month.

    Computed as ``days_in_month × 288``.  Handles leap-year February
    automatically via :func:`calendar.monthrange`.

    Args:
        year: Calendar year (e.g. 2026).
        month: Calendar month (1–12).

    Returns:
        The sample count.  Maximum possible value is 8928 (31 × 288).
    """
    _, days = calendar.monthrange(year, month)
    return days * SAMPLES_PER_DAY


def get_last_30_days(
    reference_date: date | None = None,
) -> list[dict]:
    """Return a single-element list covering the trailing 30 days ending today.

    The window runs from ``(reference_date - 29 days) 00:00 UTC`` to
    ``(reference_date + 1 day) 00:00 UTC``, inclusive of the reference date.

    Args:
        reference_date: The "today" anchor.  Defaults to ``date.today()``.

    Returns:
        A one-element list with the same dict shape as
        :func:`get_target_months`: ``year``, ``month``, ``start_ms``,
        ``end_ms``, and ``label`` (fixed to ``"last30d"``).
    """
    if reference_date is None:
        reference_date = date.today()

    end_date = reference_date + timedelta(days=1)
    start_date = end_date - timedelta(days=30)

    start_dt = datetime(start_date.year, start_date.month, start_date.day, tzinfo=timezone.utc)
    end_dt = datetime(end_date.year, end_date.month, end_date.day, tzinfo=timezone.utc)

    return [
        {
            "year": reference_date.year,
            "month": reference_date.month,
            "start_ms": int(start_dt.timestamp() * 1000),
            "end_ms": int(end_dt.timestamp() * 1000),
            "label": "last30d",
        }
    ]


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
    """Compute the 95th percentile using the ceil-rank method.

    Sorts the values and picks the element at position
    ``ceil(count * 0.95)`` (1-indexed, minimum 1).

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
    position = max(1, math.ceil(len(sorted_vals) * 0.95))
    return sorted_vals[position - 1]


def _extract_metric_data(series: list[dict], metric_name: str) -> list[int]:
    """Find a metric object in a link's series list and return its data array.

    The VCO ``metrics/getEdgeLinkSeries`` API returns each link's series
    as a list of metric objects:
    ``[{"metric": "bytesTx", "data": [v0, v1, ...]}, {"metric": "bytesRx", ...}]``

    Args:
        series: The ``"series"`` list from one link in the API response.
        metric_name: The metric to extract, e.g. ``"bytesTx"`` or ``"bytesRx"``.

    Returns:
        The ``data`` array for the named metric, or an empty list if not found.
    """
    for entry in series:
        if entry.get("metric") == metric_name:
            raw = entry.get("data") or []
            return [v if v is not None else 0 for v in raw]
    return []


def aggregate_link_samples(link_series_result: list[dict]) -> list[dict]:
    """Sum bytesTx and bytesRx across all links at each 5-minute sample index.

    Each element in ``link_series_result`` represents one link and has a
    ``"series"`` key containing metric objects of the form
    ``{"metric": "bytesTx", "data": [v0, v1, ...], "total": N}``.

    Args:
        link_series_result: List of link dicts from the VCO
            ``metrics/getEdgeLinkSeries`` API response.

    Returns:
        List of dicts with keys ``tx_bytes`` and ``rx_bytes``, one per
        sample index.  Returns an empty list when no series data exists.
    """
    tx_arrays: list[list[int]] = []
    rx_arrays: list[list[int]] = []

    for link in link_series_result:
        series = link.get("series") or []
        tx = _extract_metric_data(series, "bytesTx")
        rx = _extract_metric_data(series, "bytesRx")
        if tx:
            tx_arrays.append(tx)
        if rx:
            rx_arrays.append(rx)

    if not tx_arrays and not rx_arrays:
        return []

    max_length = max(
        (len(a) for a in tx_arrays + rx_arrays), default=0
    )
    if max_length == 0:
        return []

    aggregated: list[dict] = []
    for i in range(max_length):
        tx_total = sum(a[i] for a in tx_arrays if i < len(a))
        rx_total = sum(a[i] for a in rx_arrays if i < len(a))
        aggregated.append({"tx_bytes": tx_total, "rx_bytes": rx_total})

    return aggregated


def validate_sample_count(
    link_series_result: list[dict],
    expected_samples: int,
    *,
    strict: bool = False,
) -> dict:
    """Check that each link's data arrays have the expected number of samples.

    Iterates every bytesTx/bytesRx data array in the response and compares
    its length to ``expected_samples``.  A difference of ±1 is tolerated.

    Args:
        link_series_result: List of link dicts from the VCO
            ``metrics/getEdgeLinkSeries`` API response.
        expected_samples: The ``maxSamples`` value sent in the request.
        strict: When ``True`` and validation fails, raise :class:`ValueError`.
            Defaults to ``False`` (return the result dict silently).

    Returns:
        Dict with keys:

        - ``valid`` (bool): ``True`` if every array is within ±1.
        - ``expected`` (int): The expected sample count.
        - ``links`` (list[dict]): Per-array detail with ``link_id``,
          ``metric``, ``actual``, ``diff``, and ``ok``.

    Raises:
        ValueError: If ``strict`` is ``True`` and any array falls outside
            the ±1 tolerance.
    """
    details: list[dict] = []
    all_ok = True

    for link in link_series_result:
        link_id = link.get("linkId", "unknown")
        for entry in link.get("series") or []:
            metric = entry.get("metric", "unknown")
            data = entry.get("data") or []
            actual = len(data)
            diff = actual - expected_samples
            ok = abs(diff) <= 1
            if not ok:
                all_ok = False
            details.append({
                "link_id": link_id,
                "metric": metric,
                "actual": actual,
                "diff": diff,
                "ok": ok,
            })

    result = {
        "valid": all_ok,
        "expected": expected_samples,
        "links": details,
    }

    if strict and not all_ok:
        failures = [d for d in details if not d["ok"]]
        msg = (
            f"Sample count validation failed (expected {expected_samples}): "
            + ", ".join(
                f"link {f['link_id']} {f['metric']}={f['actual']} (diff={f['diff']})"
                for f in failures
            )
        )
        raise ValueError(msg)

    return result


def compute_daily_p95s(
    link_series_result: list[dict], start_ms: int
) -> list[dict]:
    """Compute per-day P95 bandwidth values from raw link series data.

    Aggregates samples across links, converts to Mbps, groups by UTC
    calendar day, then computes the 95th percentile for each day.

    Args:
        link_series_result: List of link dicts from the VCO
            ``metrics/getEdgeLinkSeries`` API response.
        start_ms: Start timestamp of the month in UTC milliseconds since
            epoch.  Used to assign each sample to a calendar day.

    Returns:
        List of dicts sorted by date, each with keys ``date``
        (:class:`~datetime.date`), ``sample_count`` (int),
        ``tx_p95`` (float), ``rx_p95`` (float), ``total_p95`` (float).
        Returns an empty list when no sample data is available.
    """
    samples = aggregate_link_samples(link_series_result)
    if not samples:
        return []

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

    result: list[dict] = []
    for day in sorted(daily_buckets.keys()):
        data = daily_buckets[day]
        result.append({
            "date": day,
            "sample_count": len(data["tx"]),
            "tx_p95": percentile_95(data["tx"]),
            "rx_p95": percentile_95(data["rx"]),
            "total_p95": percentile_95(data["total"]),
        })
    return result


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
        Dict with 3 keys: ``monthly_{tx,rx,total}_95th_mbps``.
        All values are 0.0 when no sample data is available.
    """
    zero_result = {
        "monthly_tx_95th_mbps": 0.0,
        "monthly_rx_95th_mbps": 0.0,
        "monthly_total_95th_mbps": 0.0,
    }

    daily_p95s = compute_daily_p95s(link_series_result, start_ms)
    if not daily_p95s:
        return zero_result

    all_daily_tx = [d["tx_p95"] for d in daily_p95s]
    all_daily_rx = [d["rx_p95"] for d in daily_p95s]
    all_daily_total = [d["total_p95"] for d in daily_p95s]

    return {
        "monthly_tx_95th_mbps": math.ceil(percentile_95(all_daily_tx)),
        "monthly_rx_95th_mbps": math.ceil(percentile_95(all_daily_rx)),
        "monthly_total_95th_mbps": math.ceil(percentile_95(all_daily_total)),
    }


def diagnose_edge_metrics(link_series_result: list[dict]) -> dict:
    """Analyze link series data quality for troubleshooting empty or zero metrics.

    Inspects the raw API response structure without modifying it, reporting
    per-link sample counts, None/zero prevalence, and whether aggregation
    produces usable data.

    Args:
        link_series_result: List of link dicts from the VCO
            ``metrics/getEdgeLinkSeries`` API response.

    Returns:
        Dict with keys:

        - ``link_count`` (int): Number of links in the response.
        - ``links`` (list[dict]): Per-link detail with ``link_id``,
          ``metrics`` (list of dicts with ``name``, ``samples``,
          ``none_count``, ``zero_count``).
        - ``total_samples_after_aggregation`` (int): Length of the
          aggregated sample list.
        - ``all_zero`` (bool): Whether every aggregated sample has
          both tx and rx equal to zero.
    """
    link_details: list[dict] = []

    for link in link_series_result:
        link_id = link.get("linkId", "unknown")
        series = link.get("series") or []
        metric_details: list[dict] = []

        for entry in series:
            metric_name = entry.get("metric", "unknown")
            raw_data = entry.get("data") or []
            none_count = sum(1 for v in raw_data if v is None)
            zero_count = sum(1 for v in raw_data if v == 0)
            metric_details.append({
                "name": metric_name,
                "samples": len(raw_data),
                "none_count": none_count,
                "zero_count": zero_count,
            })

        link_details.append({
            "link_id": link_id,
            "metrics": metric_details,
        })

    aggregated = aggregate_link_samples(link_series_result)
    all_zero = all(
        s["tx_bytes"] == 0 and s["rx_bytes"] == 0 for s in aggregated
    ) if aggregated else True

    return {
        "link_count": len(link_series_result),
        "links": link_details,
        "total_samples_after_aggregation": len(aggregated),
        "all_zero": all_zero,
    }
