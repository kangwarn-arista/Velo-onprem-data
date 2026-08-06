"""Pure computation functions for VCO bandwidth metrics.

Provides month range calculation, bytes-to-Mbps conversion,
and 95th percentile computation. Uses only Python stdlib --
no third-party dependencies.
"""
import math
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
