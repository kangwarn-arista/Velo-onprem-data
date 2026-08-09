---
phase: 04-metrics-collection-calculation
plan: "02"
subsystem: metrics-api-wiring
tags: [metrics, api-wrapper, pipeline, orchestration]
dependency_graph:
  requires: [metrics.py, tests/test_metrics.py]
  provides: [get_edge_link_series, metrics-collection-pipeline]
  affects: [vco_edge_export.py]
tech_stack:
  added: []
  patterns: [api-wrapper, conditional-pipeline, mock-testing]
key_files:
  created:
    - tests/test_metrics_api.py
  modified:
    - vco_edge_export.py
decisions:
  - "metrics_results stored as local list in __main__ -- Phase 5 will consume for CSV/zip output"
  - "edge_info_list populated conditionally only when --collect_95th is set to avoid unnecessary memory usage"
  - "Response handled with .get('result', []) default per threat model T-04-03 mitigation"
metrics:
  duration: ~10min
  completed: "2026-08-06T19:21:00Z"
  tasks_completed: 1
  tasks_total: 1
  test_count: 36
  lines_added: 120
---

# Phase 04 Plan 02: Metrics API Wiring & Collection Pipeline Summary

API wrapper for metrics/getEdgeLinkSeries with full collection pipeline wired into __main__ block, activated by --collect_95th flag, producing p95 tx/rx/total Mbps per edge per month.

## What Was Built

**get_edge_link_series function** (vco_edge_export.py) -- API wrapper that calls `metrics/getEdgeLinkSeries` with enterpriseId, edgeId, interval (start/end in ms), and metrics list (bytesTx, bytesRx). Follows the same docstring and structure pattern as existing wrappers like `get_network_license_export`.

**Edge info collection** -- During the existing enterprise/edge loop, when `--collect_95th` is active, collects edge numeric IDs and names into `edge_info_list` for downstream metrics processing.

**Metrics collection pipeline** -- After CSV write, when `--collect_95th` is set:
1. Calls `get_target_months(args.months)` to determine target month intervals
2. Iterates all edges and target months
3. Calls `get_edge_link_series` for each edge-month combination
4. Passes API response through `compute_edge_month_metrics` from Plan 04-01
5. Stores results in `metrics_results` list with enterprise_name, edge_name, month_label, and 3 p95 metrics
6. Prints progress and per-edge-month p95 values

**Test coverage** -- Created `tests/test_metrics_api.py` with 2 tests verifying the API call contract (correct method name and parameter structure) and return value pass-through.

## Task Completion

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add get_edge_link_series API wrapper and wire metrics collection | `3d45b75` | vco_edge_export.py, tests/test_metrics_api.py |

## Deviations from Plan

None -- plan executed exactly as written.

## Verification Results

- All 36 tests pass (6 CLI + 28 metrics + 2 API wrapper)
- `grep -c "def get_edge_link_series" vco_edge_export.py` returns 1
- `grep -c "metrics/getEdgeLinkSeries" vco_edge_export.py` returns 2 (wrapper + method string)
- `grep -c "from metrics import" vco_edge_export.py` returns 1
- `grep -c "compute_edge_month_metrics" vco_edge_export.py` returns 2 (import + call)
- `grep -c "metrics_results" vco_edge_export.py` returns 3 (init, append, len)
- `grep -c "edge_info_list" vco_edge_export.py` returns 3 (init, append, iterate)
- `--help` output includes both `--collect_95th` and `--months` flags
- tests/test_metrics_api.py has exactly 2 test functions
- No stubs, TODOs, or placeholder code

## Self-Check: PASSED
