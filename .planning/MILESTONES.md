# Milestones

## v1.0 — VCO Edge Export Enhancement

**Shipped:** 2026-07-28
**Archived:** 2026-08-05
**Phases:** 2 | **Plans:** 2 | **Tasks:** 4

### Accomplishments

1. Flexible VCO token prefix normalization — accepts both "Token xxx" and bare token formats
2. Network-wide license CSV export via `license/exportNetworkEdgeLicenseData` API with pandas DataFrame parsing
3. Left-join merge of license CSV with per-enterprise edge status on (Customer Name, Edge Name)
4. UTF-8 BOM CSV output for international character support in Excel

### Stats

- Files changed: 9
- Lines: +896 / -319
- Timeline: 2026-07-28 (single day)
- Branch: `vco_script_update`

### Archive

- [v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- [v1.0-REQUIREMENTS.md](milestones/v1.0-REQUIREMENTS.md)

---

## v1.1 — 95th Percentile Utilization Metrics

**Shipped:** 2026-08-08
**Archived:** 2026-08-08
**Phases:** 3 | **Plans:** 5 | **Tasks:** 9

### Accomplishments

1. argparse CLI with `--collect_95th` and `--months N` flags for opt-in metrics collection
2. Pure metrics computation module (5 functions, stdlib-only) — month ranges, bytes-to-Mbps, 95th percentile, cross-link aggregation, edge-month pipeline
3. API wrapper for `metrics/getEdgeLinkSeries` with conditional collection pipeline in `__main__`
4. Output module with per-month CSV writing (pandas left merge), VCO name extraction (urlparse), and deflated zip archive packaging
5. Full wiring with timestamped `tempfile.mkdtemp`, `try/finally` cleanup, and 53 total passing tests

### Stats

- Files changed: 29
- Lines: +3,742 / -45
- Timeline: 4 days (2026-08-05 → 2026-08-08)
- Commits: 57
- Branch: `vco_script_update`
- Test suite: 53 tests (6 CLI + 28 metrics + 2 API + 13 output + 4 wiring)

### Archive

- [v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)
- [v1.1-REQUIREMENTS.md](milestones/v1.1-REQUIREMENTS.md)

---

## v1.2 — Quick Enhancements

**Shipped:** 2026-08-08
**Archived:** 2026-08-08
**Quick Tasks:** 4 | **Commits:** 7

### Accomplishments

1. Maestro vs VCO CSV comparison tool (`compare_exports.py`) — joins on Edge Logical ID, compares serial/name/status/model/license/bandwidth with configurable tolerance
2. Max and average of daily 95th percentile metrics — 6 new summary keys alongside existing monthly P95 values
3. Trailing 30-day metrics window (`--last_30_days`) — alternative to calendar month ranges
4. Bandwidth comparison display improvements — show all rows, highlight flagged deltas with `>>>`

### Stats

- Files changed: 9
- Lines: +1,122 / -116
- Timeline: 2026-08-08 (single day)
- Commits: 7
- Branch: `vco_script_update`
- Test suite: 98 tests total (+45 from v1.1)

### Archive

- [v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md)
