# VCO On-Prem Data Export

## What This Is

Python CLI tools that export device, license, and bandwidth data from VMware VeloCloud Orchestrator (VCO) on-premises instances via JSON-RPC 2.0 API. Outputs styled Excel spreadsheets and CSV files with optional 95th percentile bandwidth metrics. Used internally by Arista for VCO fleet auditing and reporting.

## Core Value

Reliable, automated extraction of edge device and bandwidth metrics from on-prem VCO instances into analyst-friendly formats (Excel/CSV).

## Requirements

### Validated

- ✓ **EXPORT-01**: Export edge device and license data from VCO — v1.0
- ✓ **EXPORT-02**: Merge VCO license CSV with per-enterprise edge status — v1.0
- ✓ **EXPORT-03**: Collect 95th percentile bandwidth metrics per edge link — v1.0
- ✓ **EXPORT-04**: Output styled Excel spreadsheets with auto-filters and frozen panes — v1.0
- ✓ **EXPORT-05**: Support configurable month range for metrics (1–12 months) — v1.1
- ✓ **EXPORT-06**: Support trailing 30-day metrics collection — v1.1
- ✓ **EXPORT-07**: Include tx/rx columns alongside total in output — v1.1
- ✓ **EXPORT-08**: Diagnostic mode for specific edge investigation — v1.1
- ✓ **COMPARE-01**: Compare Maestro license export against VCO edge export — v1.1
- ✓ **USERS-01**: Audit all enterprise and partner/operator users across VCO — v1.0
- ✓ **BUILD-01**: Version tracking from git tags with metadata in output — v1.3
- ✓ **BUILD-02**: Package target for release bundling — v1.3
- ✓ **METRICS-01**: Align metrics calculation with PowerBI rounding logic — v1.3

### Active

- ✓ **LOG-01**: Suppress p95 metric values from stdout/logs — v1.4 Phase 1
- ✓ **LOG-02**: Suppress month count/collection mode from stdout/logs — v1.4 Phase 1
- ✓ **LOG-03**: Suppress temp directory/file paths from stdout/logs — v1.4 Phase 1
- ✓ **LOG-04**: Preserve edge processing progress output — v1.4 Phase 1
- ✓ **LOG-05**: Sanitize _metadata.json to exclude sensitive fields — v1.4 Phase 1

- ✓ **DEC-01**: Standalone offline decryption script (no project imports) — v1.4 Phase 3
- ✓ **DEC-02**: Decrypted CSVs byte-for-byte identical to originals — v1.4 Phase 3

(See REQUIREMENTS.md for remaining v1.4 scope: ENC-01–04)

### Out of Scope

(None defined yet)

## Current Milestone: v1.4 Obfuscation

**Goal:** Encrypt/obfuscate the output pipeline by default so sensitive 95th percentile metrics are never exposed in logs, temp files, or output archives — with a separate offline decryption tool for authorized recovery.

**Target features:**
- Suppress sensitive stdout/logs while preserving edge processing progress
- Sanitize metadata to exclude sensitive fields
- Ensure temp file/directory cleanup with no path leakage
- Encrypt output archive contents by default
- Provide offline decryption script for authorized metric recovery

## Context

- **Tech stack**: Python 3.13+, uv package manager, pandas, openpyxl, requests
- **API**: VCO JSON-RPC 2.0 over HTTPS (self-signed certs, SSL verify disabled)
- **Auth**: API token via .env file (VCO_URL, VCO_TOKEN)
- **Distribution**: Nuitka/PyInstaller for standalone binary builds
- **Prior milestones**: v1.0 (core export), v1.1 (metrics enhancements + comparison tool), v1.2 (quick enhancements), v1.3 (build/packaging/rounding)
- **v1.4 milestone**: Output obfuscation/encryption with offline decryption tooling

## Constraints

- **API**: VCO on-prem instances with self-signed certificates
- **Distribution**: Must produce standalone binaries for users without Python
- **Compatibility**: Output must align with Maestro field naming and PowerBI rounding

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Use uv for package management | Modern, fast Python tooling | ✓ Good |
| Disable SSL verify | On-prem VCO uses self-signed certs | ✓ Good |
| Nuitka for binary builds | Reliable single-file executables | ✓ Good |
| Align rounding with PowerBI | Users compare VCO export with PowerBI dashboards | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-08-22 after Phase 3 (Decryption Tooling) completion*
