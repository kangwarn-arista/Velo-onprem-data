# VCO On-Prem Data Export

## What This Is

Python CLI tools that export device, license, and bandwidth data from VMware VeloCloud Orchestrator (VCO) on-premises instances via JSON-RPC 2.0 API. Outputs CSV files with optional 95th percentile bandwidth metrics, field-level obfuscation by default, and standalone offline decryption. Used internally by Arista for VCO fleet auditing and reporting.

## Core Value

Reliable, automated extraction of edge device and bandwidth metrics from on-prem VCO instances into analyst-friendly formats (CSV), with obfuscation to prevent casual exposure of sensitive metrics.

## Current State

**Shipped:** v1.5 (2026-08-25)

The tool now defaults to field-level obfuscation (OBFUSCATED=1): a single combined CSV per VCO with all months packed into a 344-char Record Hash column. Three modes are available: 0=plaintext, 1=field-level (default), 2=Fernet encryption. The standalone `decrypt_metrics.py` auto-detects and reverses both field-level and Fernet formats back to per-month metric CSVs.

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
- ✓ **LOG-01**: Suppress p95 metric values from stdout/logs — v1.4
- ✓ **LOG-02**: Suppress month count/collection mode from stdout/logs — v1.4
- ✓ **LOG-03**: Suppress temp directory/file paths from stdout/logs — v1.4
- ✓ **LOG-04**: Preserve edge processing progress output — v1.4
- ✓ **LOG-05**: Sanitize _metadata.json to exclude sensitive fields — v1.4
- ✓ **ENC-01**: Compress-then-encrypt CSV output using Fernet — v1.4
- ✓ **ENC-02**: Final archive contains only _metadata.json and data.enc — v1.4
- ✓ **ENC-03**: Encryption is default; bypass with OBFUSCATED=0 — v1.4
- ✓ **ENC-04**: Temp cleanup after encryption — v1.4
- ✓ **DEC-01**: Standalone offline decryption script (no project imports) — v1.4
- ✓ **DEC-02**: Decrypted CSVs byte-for-byte identical to originals — v1.4
- ✓ **MODE-01**: 3-mode obfuscation routing (0/1/2) — v1.5
- ✓ **MODE-02**: Field-level obfuscation as default — v1.5
- ✓ **MODE-03**: Fernet mode backward-compatible — v1.5
- ✓ **MODE-04**: Sentinel Record Hash for empty UUID edges — v1.5
- ✓ **ENC-05**: Record Hash encodes metrics into fixed-length value — v1.5
- ✓ **ENC-06**: Record Hash exactly 344 characters — v1.5
- ✓ **ENC-07**: Per-edge unique Record Hash via UUID XOR key — v1.5
- ✓ **ENC-08**: Versioned extensible binary struct format — v1.5
- ✓ **OUT-01**: Combined CSV with one row per edge — v1.5
- ✓ **OUT-02**: Non-sensitive columns preserved in combined CSV — v1.5
- ✓ **OUT-03**: vco_edge_export.csv suppressed in default mode — v1.5
- ✓ **DEC-03**: Auto-detect archive format in decrypt_metrics.py — v1.5
- ✓ **DEC-04**: Decode Record Hash to original metric columns — v1.5
- ✓ **DEC-05**: decrypt_metrics.py remains standalone (zero imports) — v1.5
- ✓ **DEC-06**: Fernet decryption still works after changes — v1.5
- ✓ **TEST-01**: Round-trip fidelity for zero/max/normal values — v1.5
- ✓ **TEST-02**: Partial month data encodes/decodes correctly — v1.5

### Active

(None — no active milestone)

### Out of Scope

(None defined yet)

## Context

- **Tech stack**: Python 3.13+, uv package manager, pandas, openpyxl, requests
- **API**: VCO JSON-RPC 2.0 over HTTPS (self-signed certs, SSL verify disabled)
- **Auth**: API token via .env file (VCO_HOST, VCO_TOKEN)
- **Distribution**: Nuitka/PyInstaller for standalone binary builds
- **Prior milestones**: v1.0 (core export), v1.1 (metrics enhancements + comparison tool), v1.2 (quick enhancements), v1.3 (build/packaging/rounding), v1.4 (obfuscation/encryption), v1.5 (field-level obfuscation)

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
| Fernet with static embedded key | Obfuscation-grade sufficient; upgrade path exists | ✓ Good |
| OBFUSCATED env var for bypass | Simple toggle for authorized plaintext access | ✓ Good |
| Standalone decrypt_metrics.py | Zero project imports for offline field use | ✓ Good |
| Metadata limited to 3 keys | Prevent information disclosure in output archive | ✓ Good |
| 256-byte struct with version field | Fixed-size output, extensible for future fields (FMT-01/02) | ✓ Good |
| XOR with SHA-256(UUID) | Per-edge uniqueness without HMAC overhead; obfuscation-grade | ✓ Good |
| Combined CSV (one row per edge) | Eliminates per-month file proliferation; simpler to handle | ✓ Good |

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
*Last updated: 2026-08-25 after v1.5 milestone completed*
