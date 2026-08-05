# Roadmap: VCO Edge Export Enhancement

## Milestones

- **v1.0 MVP** — Phases 1-2 (shipped 2026-07-28)
- **v1.1 95th Percentile Utilization Metrics** — Phases 3-5 (in progress)

## Phases

<details>
<summary>v1.0 MVP (Phases 1-2) — SHIPPED 2026-07-28</summary>

- [x] **Phase 1: Data Acquisition** - Fetches license CSV and edge list from VCO API — completed 2026-07-28
- [x] **Phase 2: Merge and Output** - Merges license and edge data, outputs enriched CSV — completed 2026-07-28

</details>

### v1.1 95th Percentile Utilization Metrics (In Progress)

**Milestone Goal:** Add optional per-edge 95th percentile bandwidth metrics across configurable month ranges, output as per-month CSVs in a timestamped zip archive.

- [ ] **Phase 3: CLI & Configuration** - Argparse flags for `--collect_95th` and `--months N` without breaking existing behavior
- [ ] **Phase 4: Metrics Collection & Calculation** - Fetch per-edge link series from VCO API and compute 95th percentile tx/rx/total values
- [ ] **Phase 5: Output & Packaging** - Write per-month CSVs and compress into a timestamped zip archive

## Phase Details

### Phase 3: CLI & Configuration
**Goal**: Users can invoke the script with new flags, and existing behavior is unchanged when flags are absent
**Depends on**: Phase 2 (v1.0 complete)
**Requirements**: CLI-01, CLI-02, CLI-03, CLI-04
**Success Criteria** (what must be TRUE):
  1. User can run `vco_edge_export.py --collect_95th` and the script recognizes and accepts the flag without error
  2. User can run `vco_edge_export.py --months 3` to specify N months; omitting the flag defaults to 1 month
  3. Running without `--collect_95th` produces identical CSV output to existing v1.0 behavior
  4. Running with `--help` displays the new flags with descriptions
**Plans**: TBD

### Phase 4: Metrics Collection & Calculation
**Goal**: Per-edge 95th percentile bandwidth values (tx, rx, total) are accurately computed from VCO API data
**Depends on**: Phase 3
**Requirements**: METR-01, METR-02, METR-03, METR-04, CALC-01, CALC-02, CALC-03
**Success Criteria** (what must be TRUE):
  1. Script calls `metrics/getEdgeLinkSeries` with bytesTx and bytesRx for each edge over each target month using millisecond timestamps and the edge `id` field
  2. Target months are the last N complete calendar months — the current partial month is never included
  3. Aggregated bytes across all edge links per 5-minute sample are converted to Mbps (bytes * 8 / 1048576 / 300)
  4. Daily 95th percentile is the value at ceil(count * 0.95) in the sorted sample list, computed independently for tx, rx, and total
  5. Monthly 95th percentile is derived from daily values using the same ceil(count * 0.95) logic, accounting for variable days per month (28-31)
**Plans**: TBD

### Phase 5: Output & Packaging
**Goal**: Users receive a single zip archive containing correctly named per-month CSV files with 95th percentile columns
**Depends on**: Phase 4
**Requirements**: OUT-01, OUT-02, OUT-03, OUT-04
**Success Criteria** (what must be TRUE):
  1. Running with `--collect_95th` produces a zip archive in the working directory upon completion
  2. Each target month generates a separate CSV file named `vco_name.MM-YYYY.csv`
  3. Each CSV contains 4 additional columns: Month-Year, monthly_tx_95th_mbps, monthly_rx_95th_mbps, monthly_total_95th_mbps
  4. All CSVs are stored in a timestamped temp directory before being compressed into the zip
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Data Acquisition | v1.0 | 1/1 | Complete | 2026-07-28 |
| 2. Merge and Output | v1.0 | 1/1 | Complete | 2026-07-28 |
| 3. CLI & Configuration | v1.1 | 0/? | Not started | - |
| 4. Metrics Collection & Calculation | v1.1 | 0/? | Not started | - |
| 5. Output & Packaging | v1.1 | 0/? | Not started | - |
