# Roadmap: VCO On-Prem Data Export — v1.4 Obfuscation

## Overview

This milestone hardens the output pipeline so that sensitive 95th percentile metrics are never exposed in logs, temp files, or the output archive by default. Three sequential phases: first sanitize what the tool says out loud, then encrypt what it writes to disk, then provide an offline key to recover the data when needed.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Log Sanitization** - Suppress sensitive data from stdout/logs and sanitize metadata output (completed 2026-08-23)
- [x] **Phase 2: Output Encryption** - Encrypt the CSV archive by default and clean up temp artifacts (completed 2026-08-23)
- [x] **Phase 3: Decryption Tooling** - Standalone offline script to recover original CSVs from encrypted archive (completed 2026-08-23)

## Phase Details

### Phase 1: Log Sanitization

**Goal**: Sensitive metric values, collection parameters, and temp paths are never visible in tool output, while edge progress lines remain intact
**Depends on**: Nothing (first phase)
**Requirements**: LOG-01, LOG-02, LOG-03, LOG-04, LOG-05
**Success Criteria** (what must be TRUE):

  1. Running the export tool produces no stdout lines containing 95th percentile metric values (bandwidth numbers)
  2. Running the export tool produces no stdout lines revealing month count, collection range, or collection mode
  3. Running the export tool produces no stdout lines containing temp directory or file paths
  4. Edge processing progress lines (e.g., "Processing edge: MILPRTR01 (Hawaii State FCU)") continue to appear during execution
  5. The generated `_metadata.json` contains no months, edge count, or metric record count fields

**Plans:** 1/1 plans complete

Plans:

- [x] 01-01-PLAN.md — Suppress sensitive stdout/log output, sanitize metadata, and add verification tests

### Phase 2: Output Encryption

**Goal**: The output archive is encrypted by default so metric CSVs cannot be read without the key, with no plaintext artifacts left on disk
**Depends on**: Phase 1
**Requirements**: ENC-01, ENC-02, ENC-03, ENC-04
**Success Criteria** (what must be TRUE):

  1. The output zip from a default run contains exactly two files: `_metadata.json` and `data.enc`
  2. The `data.enc` blob is not human-readable and cannot be opened directly as a CSV or zip
  3. Running with `OBFUSCATED=0` produces unencrypted CSV files directly, without a `data.enc` blob
  4. No temp directories or intermediate CSV files remain on disk after a default export completes

**Plans:** 2/2 plans complete

Plans:
**Wave 1**

- [x] 02-01-PLAN.md — Encryption module, encrypted archive function, and tests

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 02-02-PLAN.md — Pipeline wiring with OBFUSCATED bypass and temp cleanup

### Phase 3: Decryption Tooling

**Goal**: Authorized users can recover original metric CSVs from an encrypted archive using a standalone offline script
**Depends on**: Phase 2
**Requirements**: DEC-01, DEC-02
**Success Criteria** (what must be TRUE):

  1. Running `decrypt_metrics.py <encrypted-zip>` produces CSV files on disk
  2. The decrypted CSV files are identical in content to what `OBFUSCATED=0` would have produced for the same export
  3. `decrypt_metrics.py` runs as a standalone script with no dependency on the main export project directory

**Plans:** 1/1 plans complete

Plans:

- [x] 03-01-PLAN.md — Standalone decryption script and comprehensive tests

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Log Sanitization | 1/1 | Complete   | 2026-08-23 |
| 2. Output Encryption | 2/2 | Complete   | 2026-08-23 |
| 3. Decryption Tooling | 1/1 | Complete   | 2026-08-23 |
