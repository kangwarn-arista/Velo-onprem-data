# VCO Edge Export — Binary Quick Start

This guide covers running the pre-compiled `vco_edge_export` binary. No Python or `uv` required.

---

## Setup

Place a `.env` file in the same directory as the binary:

```
VCO_HOST=<vco-hostname>
VCO_TOKEN=eyJhbGciOi...
```

- **VCO_HOST** — hostname only, e.g. `veco12-kiad1.velocloud.net` (defaults to `localhost` if not set)
- **VCO_TOKEN** — your raw API token value (do not include the `Token ` prefix)

Alternatively, pass credentials directly on the command line (no `.env` needed):

```bash
./vco_edge_export --vco-host veco12-kiad1.velocloud.net --vco-token "eyJhbGciOi..."
```

---

## Usage

### Default run (3 months of P95 metrics)

```bash
./vco_edge_export
```

Produces:
- `vco_edge_export.csv` — license data merged with edge status
- `<vco-host>_metrics_<timestamp>/` — per-month P95 bandwidth CSVs
- `<vco-host>_metrics_<timestamp>.zip` — zip archive of the above

### Change time range

```bash
# Last 1 complete calendar month
./vco_edge_export --months 1

# Last 6 complete calendar months
./vco_edge_export --months 6

# Trailing 30 days instead of calendar months
./vco_edge_export --last_30_days
```

### Skip metrics (basic export only)

```bash
SKIP_95TH=1 ./vco_edge_export
```

### Diagnose a specific edge

```bash
./vco_edge_export --diagnose "edge-name"
```

Prints diagnostic details to stdout and exits. No files are written.

### Strict sample validation

```bash
./vco_edge_export --strict_validation
```

Aborts on sample count mismatch instead of logging a warning.

---

## CLI Reference

```
./vco_edge_export [OPTIONS]

Options:
  -v, --version            Print version and exit
  --vco-host HOST          VCO hostname (overrides VCO_HOST in .env)
  --vco-token TOKEN        VCO API token (overrides VCO_TOKEN in .env)
  --months N               Months to collect, 1–12 (default: 3)
  --last_30_days           Use trailing 30 days instead of calendar months
  --all_metrics            Include tx and rx columns alongside total in CSVs
  --strict_validation      Abort on sample count mismatch
  --diagnose EDGE_NAME     Print diagnostics for a specific edge and exit
```

| Environment Variable | Description |
|---------------------|-------------|
| `VCO_HOST` | VCO hostname (default: `localhost`) |
| `VCO_TOKEN` | VCO API token |
| `SKIP_95TH` | Set to `1` to skip 95th percentile collection |

---

## Output Files

| File | When | Description |
|------|------|-------------|
| `vco_edge_export.csv` | Always | License + edge status merge |
| `<host>_metrics_<ts>/` | 95th enabled | Per-month P95 bandwidth CSVs (`30 Days 95th` by default; add `--all_metrics` for tx/rx) |
| `<host>_metrics_<ts>.zip` | 95th enabled | Zip archive of the metrics directory |
