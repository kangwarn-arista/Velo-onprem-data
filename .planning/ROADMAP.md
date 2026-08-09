# Roadmap: VCO Edge Export Enhancement

## Milestones

- ✅ **v1.0 MVP** — Phases 1-2 (shipped 2026-07-28)
- ✅ **v1.1 95th Percentile Utilization Metrics** — Phases 3-5 (shipped 2026-08-08)
- ✅ **v1.2 Quick Enhancements** — 4 quick tasks (shipped 2026-08-08)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-2) — SHIPPED 2026-07-28</summary>

- [x] **Phase 1: Data Acquisition** - Fetches license CSV and edge list from VCO API — completed 2026-07-28
- [x] **Phase 2: Merge and Output** - Merges license and edge data, outputs enriched CSV — completed 2026-07-28

</details>

<details>
<summary>✅ v1.1 95th Percentile Utilization Metrics (Phases 3-5) — SHIPPED 2026-08-08</summary>

- [x] **Phase 3: CLI & Configuration** - Argparse flags for `--collect_95th` and `--months N` (1/1 plans) — completed 2026-08-06
- [x] **Phase 4: Metrics Collection & Calculation** - Fetch per-edge link series and compute 95th percentile (2/2 plans) — completed 2026-08-06
- [x] **Phase 5: Output & Packaging** - Write per-month CSVs and compress into timestamped zip (2/2 plans) — completed 2026-08-08

</details>

<details>
<summary>✅ v1.2 Quick Enhancements (4 quick tasks) — SHIPPED 2026-08-08</summary>

- [x] **QT: compare_exports.py** - Maestro vs VCO CSV comparison tool
- [x] **QT: Max/Avg metrics** - Max and average of daily P95 values (6 new summary keys)
- [x] **QT: --last_30_days flag** - Trailing 30-day metrics window
- [x] **QT: BW comparison display** - Show all rows, highlight flagged deltas

</details>

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Data Acquisition | v1.0 | 1/1 | Complete | 2026-07-28 |
| 2. Merge and Output | v1.0 | 1/1 | Complete | 2026-07-28 |
| 3. CLI & Configuration | v1.1 | 1/1 | Complete | 2026-08-06 |
| 4. Metrics Collection & Calculation | v1.1 | 2/2 | Complete | 2026-08-06 |
| 5. Output & Packaging | v1.1 | 2/2 | Complete | 2026-08-08 |
| Quick Enhancements | v1.2 | 4 tasks | Complete | 2026-08-08 |
