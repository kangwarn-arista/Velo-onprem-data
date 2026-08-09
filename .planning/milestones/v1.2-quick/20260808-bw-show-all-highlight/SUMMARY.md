---
status: complete
completed: 2026-08-08
plan_id: 260808-bwh
---

## Summary

Changed compare_exports.py to show all bandwidth comparison rows (not just those exceeding 5.0 Mbps delta). Rows where abs(delta) >= BW_TOLERANCE_MBPS are highlighted with `>>>` in a Flag column. Only flagged rows count toward the issue total.

## Files changed
- `compare_exports.py` — updated `compare()` and `print_report()` functions

## Commits
- `15a986e` feat(quick): show all BW comparisons, highlight rows >= threshold
