# Retrospective

## Milestone: v1.0 — VCO Edge Export Enhancement

**Shipped:** 2026-07-28
**Phases:** 2 | **Plans:** 2

### What Was Built

- Flexible VCO token prefix normalization (accepts both "Token xxx" and bare token formats)
- Network-wide license CSV export via `license/exportNetworkEdgeLicenseData` with pandas DataFrame parsing
- Left-join merge of license CSV with per-enterprise edge status on (Customer Name, Edge Name)
- UTF-8 BOM CSV output for international character support in Excel

### What Worked

- Two-phase decomposition kept scope tight and each phase independently testable
- License CSV as base dataset made the merge logic clean (left join, no dropped rows)
- Dead code cleanup in Phase 2 left the script leaner than before

### What Was Inefficient

- STATE.md was not updated when Phase 2 completed — caught during milestone close
- REQUIREMENTS.md checkboxes were never checked off during phase execution

### Patterns Established

- `normalize_token()` pattern for flexible credential handling
- Network-wide API calls preferred over per-enterprise loops when available
- UTF-8 BOM (`utf-8-sig`) as default CSV encoding for Excel compatibility

### Key Lessons

- When both phases complete in one session, state files can fall out of sync — verify at milestone boundaries
- The VCO license export API provides comprehensive data that reduces the need for per-enterprise calls

## Milestone: v1.1 — 95th Percentile Utilization Metrics

**Shipped:** 2026-08-08
**Phases:** 3 | **Plans:** 5

### What Was Built

- argparse CLI with `--collect_95th` and `--months N` flags
- Pure metrics computation module (bytes-to-Mbps, 95th percentile, cross-link aggregation)
- API wrapper for `metrics/getEdgeLinkSeries` with conditional collection pipeline
- Output module with per-month CSV writing and deflated zip archive packaging
- 53 tests covering all new code

### What Worked

- TDD red-green approach caught bugs early during metrics development
- Pure function design for metrics.py made testing trivial — no mocking needed
- Conditional pipeline (only runs with `--collect_95th`) kept base workflow untouched

### What Was Inefficient

- Phase 5 took disproportionately long (~48min for 2 plans) vs Phase 3 (~4min) — output/packaging had more edge cases than expected

### Patterns Established

- Pure computation modules with no side effects for testable business logic
- `tempfile.mkdtemp` with `try/finally` for secure temp directory handling
- Left merge for metrics enrichment (unmatched edges get NaN automatically)

### Key Lessons

- Output/packaging phases often take longer than computation phases — budget accordingly
- Conditional pipeline activation via CLI flags is a clean pattern for optional features

## Milestone: v1.2 — Quick Enhancements

**Shipped:** 2026-08-08
**Quick Tasks:** 4 | **Commits:** 7

### What Was Built

- Maestro vs VCO CSV comparison tool (`compare_exports.py`)
- Max/avg of daily P95 metrics (6 new summary keys)
- `--last_30_days` trailing 30-day metrics window
- BW comparison display improvements (show all, highlight flagged)

### What Worked

- Quick task workflow for small, self-contained enhancements — no formal phase overhead
- Incremental test additions maintained coverage (53 → 98 tests)
- Each quick task was independently committable and testable

### What Was Inefficient

- Nothing notable — quick tasks were appropriately scoped

### Patterns Established

- Quick tasks as a lightweight milestone for post-release polishing
- Standalone comparison scripts for cross-system validation

### Key Lessons

- Post-milestone quick tasks are an effective pattern for small enhancements that don't warrant full phase planning
- Bundling quick tasks into a lightweight milestone keeps the project history clean

## Cross-Milestone Trends

| Milestone | Phases | Plans | Duration | Key Theme |
|-----------|--------|-------|----------|-----------|
| v1.0 | 2 | 2 | 1 day | Data pipeline + merge |
| v1.1 | 3 | 5 | 4 days | Metrics collection + calculation |
| v1.2 | 0 (4 QTs) | 0 | 1 day | Quick enhancements + comparison tool |
