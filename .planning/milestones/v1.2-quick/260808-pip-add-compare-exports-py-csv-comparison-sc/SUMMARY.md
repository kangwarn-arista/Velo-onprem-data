---
quick_id: "260808-pip"
description: "Add compare_exports.py CSV comparison script"
status: complete
completed: 2026-08-08
---

# Summary: Add compare_exports.py CSV comparison script

## What was done
Added `compare_exports.py` — a CLI tool that compares Maestro license export CSV against VCO edge export CSV.

## Key features
- Joins on `Edge Logical ID` (Maestro) ↔ `Edge UUID` (VCO export) — 100% match rate
- Deduplicates VCO rows to latest `Month-Year` per edge before comparing
- Compares: serial number, edge name, status, model, license SKU
- Bandwidth 95th percentile comparison with configurable tolerance (default 5 Mbps)
- Enterprise name filter (case-insensitive substring match)
- Exit code 0 if clean, 1 if issues found

## Usage
```bash
uv run python compare_exports.py <maestro_csv> <vco_csv> <enterprise_name>
```

## Files changed
- `compare_exports.py` (new)

## Commits
- `e343746` feat: add compare_exports.py for Maestro vs VCO CSV comparison
- `4f0121b` docs(quick-260808-pip): Add compare_exports.py CSV comparison script
