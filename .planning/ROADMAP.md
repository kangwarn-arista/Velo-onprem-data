# Roadmap: VCO Edge Export Enhancement

## Milestones

- ✅ **v1.0 MVP** — Phases 1-2 (shipped 2026-07-28)
- ✅ **v1.1 95th Percentile Utilization Metrics** — Phases 3-5 (shipped 2026-08-08)

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

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Data Acquisition | v1.0 | 1/1 | Complete | 2026-07-28 |
| 2. Merge and Output | v1.0 | 1/1 | Complete | 2026-07-28 |
| 3. CLI & Configuration | v1.1 | 1/1 | Complete | 2026-08-06 |
| 4. Metrics Collection & Calculation | v1.1 | 2/2 | Complete | 2026-08-06 |
| 5. Output & Packaging | v1.1 | 2/2 | Complete | 2026-08-08 |
