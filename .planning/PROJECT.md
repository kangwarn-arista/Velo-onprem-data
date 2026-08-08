# VCO Edge Export Enhancement

## What This Is

A Python CLI tool that exports edge device and license data from VMware VeloCloud Orchestrator (VCO) on-premises instances via JSON-RPC 2.0 API. It merges network-wide license CSV export data with per-enterprise edge status into a single enriched CSV report.

## Core Value

Produce a single, accurate CSV report combining VCO license CSV export data with edge device status — joined reliably across enterprises.

## Requirements

### Validated

- Fetches all enterprises from VCO via `network/getNetworkEnterprises` — existing
- Fetches edge devices per enterprise with site/HA/config/link metadata — existing
- Loads credentials from `.env` file with startup validation — existing
- Disables SSL verification for self-signed on-prem certs — existing
- Flexible token format: accept both "Token xxx" and bare "xxx", auto-prepend "Token " when missing — v1.0
- Call `license/exportNetworkEdgeLicenseData` API to get license CSV data — v1.0
- Parse the CSV string from `result.csv` response field into a DataFrame — v1.0
- Merge license CSV data with edge status using (Customer Name, Edge Name) as join key — v1.0
- Use license CSV as the base dataset, enrich with Edge Status from edge loop — v1.0
- Print warnings for unmatched edges where join fails, leave Edge Status blank — v1.0
- Output as CSV with UTF-8 BOM encoding for international character support — v1.0

### Active

None — all v1.1 requirements validated.

### Recently Validated (v1.1)

- CLI argument parsing for `--collect_95th` and `--months N` — Phase 03
- Per-edge link metrics collection via `metrics/getEdgeLinkSeries` API — Phase 04
- Bytes-to-Mbps conversion with cross-link aggregation — Phase 04
- Daily and monthly 95th percentile calculation — Phase 04
- Per-month CSV output with metrics columns — Phase 05
- Timestamped temp directory and zip compression — Phase 05

## Current Milestone: v1.1 95th Percentile Utilization Metrics

**Goal:** Add optional per-edge 95th percentile bandwidth utilization metrics (tx, rx, total) across configurable month ranges, output as per-month CSVs in a timestamped zip archive.

**Target features:**
- CLI argument parsing (`--collect_95th`, `--months N`)
- Per-edge link metrics collection via `metrics/getEdgeLinkSeries` API
- Bytes-to-Mbps conversion with cross-link aggregation (sum all links per sample)
- Daily 95th percentile calculation (~288 samples/day, pick 274th sorted value)
- Monthly 95th percentile from daily values (variable days/month)
- Per-month CSV output: 4 additional columns (Month-Year, monthly_tx_95th_mbps, monthly_rx_95th_mbps, monthly_total_95th_mbps)
- Output naming: `vco_name.MM-YYYY.csv`
- Timestamped temp directory + zip compression
- Last N complete months (never current partial month)

### Out of Scope

- Multi-VCO support — single VCO instance per run is sufficient for now
- Rich Excel formatting (styled headers, colors) — CSV output is the v1.0 deliverable
- Refactoring shared code with `get_all_users.py` — focus on `vco_edge_export.py` only
- Concurrent/async API calls — sequential is acceptable for this data volume
- Unit tests — no testing infrastructure; not requested

## Context

Shipped v1.0 with 678 LOC across 3 Python files.
Tech stack: Python 3.13, requests, pandas, openpyxl, python-dotenv, managed via `uv`.
Output: `vco_edge_export.csv` (enriched license+edge-status report).
The `get_all_users.py` script was enhanced with auth detection and retry logic but is otherwise unchanged in scope.

## Constraints

- **Auth:** VCO API token via `.env`, SSL verification disabled for self-signed certs
- **Python:** 3.13+, managed via `uv`
- **Network ID:** Hardcoded to 1 (single-network VCO deployments)
- **Git:** No commits to main branch — work on a feature branch

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| License CSV as base dataset | Contains the authoritative license data; edge loop only adds status | Good — clean separation of concerns |
| Join on (Customer Name, Edge Name) | License CSV lacks Edge Logical ID; name-based join is the only common key | Good — works reliably |
| Warn on join failures, don't drop rows | Missing status is acceptable; missing license data is not | Good — no data loss |
| CSV output instead of Excel | Simpler, no openpyxl dependency for edge export | Good — UTF-8 BOM handles international chars |
| Dead code removal after merge refactor | 5 functions became unreachable; keeping them would be misleading | Good — cleaner codebase |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? Move to Out of Scope with reason
2. Requirements validated? Move to Validated with phase reference
3. New requirements emerged? Add to Active
4. Decisions to log? Add to Key Decisions
5. "What This Is" still accurate? Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-08-05 after v1.1 milestone start*
