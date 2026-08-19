# VCO Edge Export - Usage Guide

## Overview

`vco_edge_export.py` exports edge device and license data from a VMware VeloCloud Orchestrator (VCO) on-premises instance. It merges the VCO network-wide license CSV export with per-enterprise edge status and computes 95th percentile bandwidth metrics per edge per month.

## Prerequisites

- Python 3.13+
- `uv` package manager

Install dependencies:

```bash
uv add requests pandas openpyxl python-dotenv
```

## Configuration

### Option 1: Environment file (`.env`)

Create a `.env` file in the same directory as the script:

```
VCO_HOST=veco12-kiad1.velocloud.net
VCO_TOKEN=Token eyJhbGciOi...
```

### Option 2: Command-line arguments

Pass credentials directly on the command line:

```bash
uv run python vco_edge_export.py --vco-host veco12-kiad1.velocloud.net --vco-token "Token eyJhbGciOi..."
```

Command-line arguments override the `.env` values when both are provided.

### What to use for `--vco-host`

The `--vco-host` value is the **hostname only** of your VCO instance, without `https://` or any path. The script automatically constructs the full API URL.

| Correct | Incorrect |
|---------|-----------|
| `veco12-kiad1.velocloud.net` | `https://veco12-kiad1.velocloud.net/portal` |
| `vco.company.com` | `vco.company.com/portal/` |

### What to use for `--vco-token`

The `--vco-token` value is your VCO API token. You can provide it with or without the `Token ` prefix - the script adds it automatically if missing.

```bash
# Both of these work:
--vco-token "Token eyJhbGciOi..."
--vco-token "eyJhbGciOi..."
```

To generate an API token, log into your VCO portal and navigate to your user profile settings.

## Basic Usage

Run the script with defaults (collects 95th percentile metrics for the last complete calendar month):

```bash
uv run python vco_edge_export.py
```

## Command-Line Options

```
--vco-host HOST       VCO hostname (overrides VCO_HOST in .env)
--vco-token TOKEN     VCO API token (overrides VCO_TOKEN in .env)
--months N            Number of complete calendar months to collect (default: 1, max: 12)
--last_30_days        Collect metrics for the trailing 30 days instead of calendar months
--strict_validation   Abort on sample count mismatch instead of logging a warning
--diagnose EDGE_NAME  Print detailed diagnostic output for a specific edge and exit
```

`--months` and `--last_30_days` are mutually exclusive.

## Examples

### Collect last 3 complete months of metrics

```bash
uv run python vco_edge_export.py --months 3
```

### Collect trailing 30 days of metrics

```bash
uv run python vco_edge_export.py --last_30_days
```

### Override VCO credentials

```bash
uv run python vco_edge_export.py \
  --vco-host vco-prod.company.net \
  --vco-token "Token abc123..."
```

### Diagnose a specific edge

```bash
uv run python vco_edge_export.py --diagnose "WKEPRTR01"
```

This prints detailed per-link sample data, daily P95 values, and monthly P95 calculations for the named edge, then exits.

## Output

The script produces:

1. **`vco_edge_export.csv`** - Merged license and edge status data for all edges across all enterprises.
2. **`{vco_host}_metrics_{timestamp}/`** - Directory containing one CSV per month with 95th percentile bandwidth metrics (tx, rx, total) merged with the license/status data.
3. **`{vco_host}_metrics_{timestamp}.zip`** - Zip archive of the metrics CSV directory.

## Troubleshooting

- **"VCO_HOST not found"**: Set `VCO_HOST` in `.env` or pass `--vco-host`.
- **"VCO_TOKEN not found"**: Set `VCO_TOKEN` in `.env` or pass `--vco-token`.
- **"Authentication failed (HTTP 401/403)"**: Your token is invalid or expired. Generate a new one from the VCO portal.
- **"No enterprises returned"**: Typically indicates an auth issue. Verify your token has the correct permissions.
- **Use `--diagnose EDGE_NAME`** to investigate why a specific edge shows zero or missing metrics.
