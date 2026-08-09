---
gsd_plan_version: 1
plan_id: 260807-q4m
phase: quick/add-max-avg-metrics
milestone: v1.1
created: 2026-08-08
model: claude-opus-4-6
---

## Objective

Add max and average of daily 95th percentile values to `compute_edge_month_metrics` in `metrics.py`, producing 6 new summary keys alongside the existing monthly p95 keys. Update the logging output and tests to cover the new keys.

## Tasks

### T1 — Update tests for new metric keys (TDD red phase)

- **id:** T1
- **title:** Add test assertions for 6 new max/avg metric keys
- **file:** tests/test_metrics.py
- **what:**
  - In `TestComputeEdgeMonthMetrics`:
    - Update `test_empty_link_series_returns_zeros`: assert the 6 new keys (`monthly_tx_max_mbps`, `monthly_rx_max_mbps`, `monthly_total_max_mbps`, `monthly_tx_avg_mbps`, `monthly_rx_avg_mbps`, `monthly_total_avg_mbps`) are all 0.0.
    - Update `test_result_has_three_keys` to `test_result_has_nine_keys`: assert `set(result.keys())` equals the full set of 9 keys (3 existing p95 + 6 new).
    - Update `test_uniform_data_288_samples`: for uniform data the max and avg equal the p95. Assert all 6 new keys match the corresponding p95 value (`pytest.approx`).
    - Update `test_multi_day_grouping`: Day 1 p95 = 8/300, Day 2 p95 = 16/300. The expected max is 16/300 (max of [8/300, 16/300]) and the expected avg is (8/300 + 16/300) / 2 = 12/300. Assert `monthly_tx_max_mbps == pytest.approx(16/300)` and `monthly_tx_avg_mbps == pytest.approx(12/300)`. rx and total are 0.0 for max/avg since rx bytes are 0 (uniform single-sample p95 of zeros).
  - Run tests: `uv run pytest tests/test_metrics.py -x`. Expect failures (red phase).
- **done_when:** Tests are written and fail because `metrics.py` does not yet return the new keys.
- **depends_on:** none

### T2 — Implement max and avg computation in metrics.py

- **id:** T2
- **title:** Add max/avg of daily p95 lists to compute_edge_month_metrics return dict
- **file:** metrics.py
- **what:**
  - In `compute_edge_month_metrics`, update `zero_result` to include the 6 new keys with value 0.0: `monthly_tx_max_mbps`, `monthly_rx_max_mbps`, `monthly_total_max_mbps`, `monthly_tx_avg_mbps`, `monthly_rx_avg_mbps`, `monthly_total_avg_mbps`.
  - After the loop that builds `all_daily_tx`, `all_daily_rx`, `all_daily_total` (after line 207), compute:
    - `max(all_daily_tx)`, `max(all_daily_rx)`, `max(all_daily_total)` for the max keys.
    - `sum(all_daily_tx) / len(all_daily_tx)` (and same for rx, total) for the avg keys. Use `statistics.mean` or manual sum/len -- either is fine since the lists are guaranteed non-empty at that point (early return on empty samples guards this).
  - Add these 6 values to the return dict alongside the existing 3 p95 keys.
  - Update the module docstring's description of `compute_edge_month_metrics` return value to mention the 6 new keys.
  - Run tests: `uv run pytest tests/test_metrics.py -x`. All tests must pass (green phase).
- **done_when:** `uv run pytest tests/test_metrics.py -x` passes with 0 failures. The return dict has 9 keys total.
- **depends_on:** T1

### T3 — Update logging line in vco_edge_export.py

- **id:** T3
- **title:** Extend the metrics print line to show max and avg values
- **file:** vco_edge_export.py
- **what:**
  - At lines 412-417, extend the f-string print statement to also log the new max and avg values. Use this format (keeping the existing p95 line, adding max and avg on new lines):
    ```
    {month['label']}: p95 tx={...:.4f} rx={...:.4f} total={...:.4f} | max tx={...:.4f} rx={...:.4f} total={...:.4f} | avg tx={...:.4f} rx={...:.4f} total={...:.4f} Mbps
    ```
    Reference the 6 new keys from the `metrics` dict: `monthly_tx_max_mbps`, `monthly_rx_max_mbps`, `monthly_total_max_mbps`, `monthly_tx_avg_mbps`, `monthly_rx_avg_mbps`, `monthly_total_avg_mbps`.
  - Run full test suite: `uv run pytest tests/ -x` to ensure nothing is broken.
- **done_when:** `uv run pytest tests/ -x` passes. The print statement references all 9 metric keys.
- **depends_on:** T2

## Commit Convention

- T1: `test(quick): add assertions for max/avg metric keys`
- T2: `feat(quick): add max and avg of daily p95 to compute_edge_month_metrics`
- T3: `feat(quick): update metrics log line with max and avg values`
