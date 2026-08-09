---
status: complete
completed: 2026-08-08
plan_id: 260807-q4m
---

## Summary

Added max and average of daily 95th percentile values to the metrics pipeline, producing 6 new summary keys (`monthly_{tx,rx,total}_{max,avg}_mbps`) alongside the existing monthly P95 keys.

## Changes

### metrics.py
- Added `max_samples_for_month()` for calendar-aware sample counts
- Extracted `_extract_metric_data()` helper for new VCO series format
- Added `validate_sample_count()` for data quality checks
- Extracted `compute_daily_p95s()` from the monolithic pipeline
- Updated `compute_edge_month_metrics()` to return 9 keys (3 P95 + 3 max + 3 avg)
- Added `diagnose_edge_metrics()` for troubleshooting data quality
- Refactored `aggregate_link_samples()` for metric-object series format

### output.py
- Added 6 new metric columns to CSV writer

### vco_edge_export.py
- Extended metrics print line with max and avg values

### Tests
- 57 metrics tests covering all new functions
- Updated output, wiring, and CLI tests for 9-key metrics

## Commits

- `d9bd366` feat(quick): add max/avg metrics, daily P95s, validation, and diagnostics
- `1e85b27` feat(quick): wire max/avg metrics through output and export pipeline
