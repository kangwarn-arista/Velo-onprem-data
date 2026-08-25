# Requirements: VCO On-Prem Data Export

**Defined:** 2026-08-22
**Core Value:** Reliable, automated extraction of edge device and bandwidth metrics from on-prem VCO instances into analyst-friendly formats (Excel/CSV).

## v1.4 Requirements

Requirements for milestone v1.4: Obfuscation. Each maps to roadmap phases.

### Log Sanitization

- [ ] **LOG-01**: Suppress all stdout/log messages that reveal 95th percentile metric values
- [ ] **LOG-02**: Suppress messages revealing number of months collected or collection mode
- [ ] **LOG-03**: Suppress display of temp directory/file paths in stdout/logs
- [ ] **LOG-04**: Preserve edge processing progress output (e.g. "Processing edge: MILPRTR01 (Hawaii State FCU)")
- [ ] **LOG-05**: Sanitize `_metadata.json` to exclude sensitive fields (months, edge count, metric record count)

### Output Encryption

- [x] **ENC-01**: Compress-then-encrypt CSV output as a single encrypted blob using Fernet (AES-128-CBC + HMAC)
- [x] **ENC-02**: Final zip archive contains only sanitized `_metadata.json` and encrypted `data.enc`
- [x] **ENC-03**: Encryption is the default behavior; bypass only when `OBFUSCATED=0` is set
- [x] **ENC-04**: Temp directories and intermediate CSV files are deleted after encryption

### Decryption Tooling

- [ ] **DEC-01**: Standalone `decrypt_metrics.py` script that takes an encrypted zip and recovers original CSVs
- [ ] **DEC-02**: Decrypted output is identical to what `OBFUSCATED=0` would produce

## Future Requirements

(None deferred)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Password-based key derivation | Static key sufficient for obfuscation-grade; upgrade path exists if needed later |
| Encrypting the main `vco_edge_export.csv` | Only the 95th percentile metrics output needs protection |
| Encrypting diagnostic mode output | Diagnostic is a dev/debug tool, not a deliverable |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| LOG-01 | Phase 1 | Pending |
| LOG-02 | Phase 1 | Pending |
| LOG-03 | Phase 1 | Pending |
| LOG-04 | Phase 1 | Pending |
| LOG-05 | Phase 1 | Pending |
| ENC-01 | Phase 2 | Complete |
| ENC-02 | Phase 2 | Complete |
| ENC-03 | Phase 2 | Complete |
| ENC-04 | Phase 2 | Complete |
| DEC-01 | Phase 3 | Pending |
| DEC-02 | Phase 3 | Pending |

**Coverage:**
- v1.4 requirements: 11 total
- Mapped to phases: 11
- Unmapped: 0 ✓

---
*Requirements defined: 2026-08-22*
*Last updated: 2026-08-22 after roadmap creation (v1.4)*
