---
gsd_plan_version: 1
plan_id: 260808-l30
phase: quick/add-last-30-days-flag
milestone: v1.1
created: 2026-08-08
model: claude-opus-4-6
---

## Objective

Add `--last_30_days` CLI flag. When specified (with `--collect_95th`), the time window covers the trailing 30 days ending at end-of-today UTC instead of complete calendar months. The output label is `"last30d"` instead of `"MM-YYYY"`.

## Design

The `target_months` list already drives everything — API calls, metrics computation, output labeling. A "last 30 days" window is just a single-element list with the same dict shape (`year`, `month`, `start_ms`, `end_ms`, `label`) but custom values:

- `start_ms` = (today - 29 days) at 00:00:00 UTC
- `end_ms` = (today + 1 day) at 00:00:00 UTC (i.e. end of today)
- `label` = `"last30d"`
- `year`/`month` = today's year/month (used only for `max_samples_for_month` — we compute samples as 30 × 288 = 8640 instead)

New function `get_last_30_days()` in `metrics.py` returns this single-element list.

`--last_30_days` is mutually exclusive with `--months` (argparse mutual exclusion group).

## Tasks

### T1 — Add tests for get_last_30_days and CLI flag (TDD red phase)

- **id:** T1
- **file:** tests/test_metrics.py, tests/test_cli.py
- **what:**
  - In test_metrics.py: add `TestGetLast30Days` class testing:
    - Returns a single-element list
    - Label is "last30d"
    - start_ms is 30 days before end-of-today
    - end_ms is end-of-today (midnight next day)
    - Has all expected keys
  - In test_cli.py: add tests for:
    - `--last_30_days` flag defaults to False
    - `--last_30_days` flag sets last_30_days=True
    - `--last_30_days` with `--months` is rejected (SystemExit)
    - help text contains `--last_30_days`
  - Run tests: expect failures (red phase)
- **done_when:** Tests written and failing
- **depends_on:** none

### T2 — Implement get_last_30_days in metrics.py

- **id:** T2
- **file:** metrics.py
- **what:**
  - Add `get_last_30_days(reference_date=None)` function returning a single-element list with the dict shape matching `get_target_months`.
  - Run `uv run pytest tests/test_metrics.py -x`
- **done_when:** Metrics tests pass
- **depends_on:** T1

### T3 — Add --last_30_days CLI flag and wire it through

- **id:** T3
- **file:** vco_edge_export.py, tests/test_cli.py
- **what:**
  - Add `--last_30_days` to `build_parser()` using a mutually exclusive group with `--months`
  - In `__main__`, when `args.last_30_days` is True, use `get_last_30_days()` instead of `get_target_months(args.months)`
  - For sample count: use `30 * 288 = 8640` instead of `max_samples_for_month()`
  - Run full test suite
- **done_when:** `uv run pytest tests/ -x` passes
- **depends_on:** T2

## Commit Convention

- T1: `test(quick): add tests for --last_30_days flag and get_last_30_days`
- T2: `feat(quick): add get_last_30_days to metrics.py`
- T3: `feat(quick): wire --last_30_days flag through CLI and export pipeline`
