# Requirements: VCO Edge Export Enhancement

**Defined:** 2026-08-05
**Core Value:** Produce a single, accurate CSV report combining VCO license CSV export data with edge device status — joined reliably across enterprises.

## v1.1 Requirements

Requirements for milestone v1.1: 95th Percentile Utilization Metrics.

### CLI & Configuration

- [ ] **CLI-01**: User can pass `--collect_95th` flag to enable 95th percentile metrics collection
- [ ] **CLI-02**: User can pass `--months N` to specify number of months to collect (default 1)
- [ ] **CLI-03**: Script uses argparse for clean CLI argument handling
- [ ] **CLI-04**: Without `--collect_95th`, script produces existing CSV output unchanged

### Metrics Collection

- [ ] **METR-01**: Script calls `metrics/getEdgeLinkSeries` per edge with bytesTx and bytesRx stats for each target month (timestamps in milliseconds, edge `id` field)
- [ ] **METR-02**: Month range is last N complete months from today (never current partial month)
- [ ] **METR-03**: Script sums bytesTx/bytesRx across all links per edge at each 5-minute sample point
- [ ] **METR-04**: Script converts aggregated bytes to Mbps: bytes * 8 / 1048576 / 300

### 95th Percentile Calculation

- [ ] **CALC-01**: Script computes daily 95th percentile by sorting ~288 samples per day and picking value at ceil(count * 0.95) position for tx, rx, and total Mbps
- [ ] **CALC-02**: Script computes monthly 95th percentile from daily 95th values, accounting for variable days per month (28-31 days), using same ceil(count * 0.95) logic
- [ ] **CALC-03**: Script produces 3 metrics per edge per month: monthly_tx_95th_mbps, monthly_rx_95th_mbps, monthly_total_95th_mbps

### Output

- [ ] **OUT-01**: Script produces one CSV per month with 4 additional columns: Month-Year, monthly_tx_95th_mbps, monthly_rx_95th_mbps, monthly_total_95th_mbps
- [ ] **OUT-02**: CSV files named as `vco_name.MM-YYYY.csv`
- [ ] **OUT-03**: Output stored in timestamped temp directory based on script run time
- [ ] **OUT-04**: All output files compressed into a single zip archive at the end

## Future Requirements

### Enhanced Metrics

- **EMETR-01**: Support for additional percentile values (e.g., 50th, 99th)
- **EMETR-02**: Per-link breakdown in addition to aggregated edge metrics

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real-time/streaming metrics | Batch export is sufficient for reporting |
| Multi-VCO support | Single VCO instance per run |
| Interactive dashboard/visualization | CLI CSV output covers the use case |
| Concurrent API calls | Sequential is acceptable for this data volume |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CLI-01 | TBD | Pending |
| CLI-02 | TBD | Pending |
| CLI-03 | TBD | Pending |
| CLI-04 | TBD | Pending |
| METR-01 | TBD | Pending |
| METR-02 | TBD | Pending |
| METR-03 | TBD | Pending |
| METR-04 | TBD | Pending |
| CALC-01 | TBD | Pending |
| CALC-02 | TBD | Pending |
| CALC-03 | TBD | Pending |
| OUT-01 | TBD | Pending |
| OUT-02 | TBD | Pending |
| OUT-03 | TBD | Pending |
| OUT-04 | TBD | Pending |

**Coverage:**
- v1.1 requirements: 15 total
- Mapped to phases: 0
- Unmapped: 15

---
*Requirements defined: 2026-08-05*
*Last updated: 2026-08-05 after initial definition*
