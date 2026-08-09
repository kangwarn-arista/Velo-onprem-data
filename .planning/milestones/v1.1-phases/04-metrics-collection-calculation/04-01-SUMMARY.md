---
phase: 04-metrics-collection-calculation
plan: "01"
subsystem: metrics-computation
tags: [metrics, percentile, bandwidth, pure-functions, tdd]
dependency_graph:
  requires: []
  provides: [metrics.py, tests/test_metrics.py]
  affects: [vco_edge_export.py]
tech_stack:
  added: []
  patterns: [tdd-red-green, pure-functions, stdlib-only]
key_files:
  created:
    - metrics.py
    - tests/test_metrics.py
  modified: []
decisions:
  - "Used collections.defaultdict for daily bucket grouping -- cleaner than manual dict init"
  - "total_mbps computed from raw bytes sum (tx+rx) before conversion, not sum of converted values"
  - "Epoch timestamps hardcoded in tests verified against Python datetime to avoid drift"
metrics:
  duration: ~5min
  completed: "2026-08-06T05:24:20Z"
  tasks_completed: 2
  tasks_total: 2
  test_count: 28
  lines_added: 461
---

# Phase 04 Plan 01: Metrics Computation Module Summary

Pure metrics computation module with 5 functions covering month ranges, bytes-to-Mbps conversion, 95th percentile, cross-link aggregation, and the full edge-month pipeline -- all stdlib-only with 28 tests.

## What Was Built

Created `metrics.py` at repo root with 5 exported pure functions:

1. **get_target_months** -- Returns last N complete calendar months with UTC millisecond timestamps; excludes current partial month
2. **bytes_to_mbps** -- Converts 5-minute byte count to Mbps using `bytes * 8 / 1_048_576 / 300`
3. **percentile_95** -- Ceiling-rank method: `ceil(count * 0.95)` position (1-indexed), raises ValueError on empty input
4. **aggregate_link_samples** -- Sums bytesTx/bytesRx across all links at each 5-minute sample index; defaults missing keys to 0
5. **compute_edge_month_metrics** -- Full pipeline: aggregate links, convert to Mbps, group by UTC day, compute daily p95, compute monthly p95 from daily values

Created `tests/test_metrics.py` with 28 test functions across 5 test classes. All tests pass (34 total including 6 existing CLI tests).

## Task Completion

| Task | Name | Commits | Files |
|------|------|---------|-------|
| 1 | Core computation functions | `77f6470` (RED), `033aa74` (GREEN) | metrics.py, tests/test_metrics.py |
| 2 | Link aggregation and edge-month metrics pipeline | `1b46937` (RED), `3dee235` (GREEN) | metrics.py, tests/test_metrics.py |

## TDD Gate Compliance

Both tasks followed RED/GREEN cycle:

- Task 1: `test(04-01)` commit `77f6470` (RED) followed by `feat(04-01)` commit `033aa74` (GREEN)
- Task 2: `test(04-01)` commit `1b46937` (RED) followed by `feat(04-01)` commit `3dee235` (GREEN)

All RED phases confirmed failing tests (ImportError). All GREEN phases confirmed all tests passing.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed hardcoded epoch constants in test**
- **Found during:** Task 1 GREEN phase
- **Issue:** Test hardcoded `1782950400` for 2026-07-01 UTC and `1785628800` for 2026-08-01 UTC; correct values are `1782864000` and `1785542400`
- **Fix:** Verified correct epochs via `datetime(2026, 7, 1, tzinfo=timezone.utc).timestamp()` and updated test assertions
- **Files modified:** tests/test_metrics.py
- **Commit:** 033aa74

## Verification Results

- All 5 functions importable from metrics
- 34 tests pass (6 CLI + 28 metrics)
- No third-party imports in metrics.py (stdlib only: math, collections, datetime)
- No stubs, TODOs, or placeholder code

## Self-Check: PASSED
