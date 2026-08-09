---
status: complete
completed: 2026-08-08
plan_id: 260808-l30
---

## Summary

Added `--last_30_days` CLI flag. When specified with `--collect_95th`, the metrics time window covers the trailing 30 days (including today) instead of complete calendar months. Output label is `"last30d"`.

## Changes

### metrics.py
- Added `get_last_30_days(reference_date=None)` returning a single-element list with the same dict shape as `get_target_months`

### vco_edge_export.py
- Added `--last_30_days` flag (mutually exclusive with `--months`) to `build_parser()`
- Wired through both diagnose mode and normal metrics collection
- Sample count uses `30 × 288 = 8640` instead of calendar-month-based count

### Tests
- 8 tests for `get_last_30_days` (window span, label, keys, defaults)
- 4 CLI tests (default value, flag, mutual exclusion with --months, help text)

## Usage
```bash
uv run python vco_edge_export.py --collect_95th --last_30_days
```

## Commits

- `08c8b6f` feat(quick): add get_last_30_days to metrics.py
- `bbf3df3` feat(quick): wire --last_30_days flag through CLI and export pipeline
