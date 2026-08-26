# Decrypt Metrics — Usage Guide

Standalone offline tool for recovering metric CSVs from the output archives produced by `vco_edge_export`. Requires only Python 3.13+ and the `cryptography` package — no project imports needed.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Usage](#usage)
  - [Encrypted Archive (Full File Encryption)](#encrypted-archive-full-file-encryption)
  - [Combined CSV (Field-Level Encoding)](#combined-csv-field-level-encoding)
  - [Auto-Detection](#auto-detection)
- [Output Files](#output-files)
- [CLI Reference](#cli-reference)
- [Error Handling](#error-handling)

---

## Overview

`vco_edge_export` can produce output in two formats:

1. **Encrypted archive** — a zip file containing a Fernet-encrypted payload (`data.enc`). The inner payload is itself a zip of per-month CSV files.
2. **Combined CSV** — a single CSV file with one row per edge, where per-month metric data is encoded into a `Record Hash` column.

`decrypt_metrics.py` reverses both formats, producing plain per-month CSV files with human-readable metric columns.

## Prerequisites

- Python 3.13+
- [`uv`](https://docs.astral.sh/uv/) package manager (or the `cryptography` package installed manually)

No VCO access or API token is needed — decryption is fully offline.

## Usage

### Encrypted Archive (Full File Encryption)

When `vco_edge_export` produces an encrypted zip archive, the internal structure is:

```
outer.zip
├── data.enc          # Fernet-encrypted inner zip bytes
└── _metadata.json    # Archive metadata (version, VCO host, timestamp)
```

To decrypt and extract:

```bash
uv run python decrypt_metrics.py export.zip
```

This decrypts `data.enc`, unpacks the inner zip, and writes the original per-month CSV files to a directory named after the archive:

```
export/
├── vco116.06-2026.csv
├── vco116.07-2026.csv
└── vco116.08-2026.csv
```

#### Specifying an output directory

```bash
uv run python decrypt_metrics.py export.zip /path/to/output
```

CSV files are extracted into the specified directory instead of the default.

### Combined CSV (Field-Level Encoding)

When `vco_edge_export` produces a combined CSV, each edge's per-month metrics are encoded into a single `Record Hash` column. The file has one row per edge:

```
Edge UUID,Edge Name,Customer Name,...,Record Hash
550e8400-...,edge1,Acme Corp,...,YWJjZGVm...
```

To decode:

```bash
uv run python decrypt_metrics.py vco116.combined.csv
```

This decodes each `Record Hash` back into per-month metric values and writes one CSV file per month:

```
vco116.combined/
├── vco116.06-2026.csv
├── vco116.07-2026.csv
└── vco116.08-2026.csv
```

Each per-month CSV replaces the `Record Hash` column with three readable columns:

| Column | Description |
|--------|-------------|
| `Month-Year` | Month label (e.g. `07-2026` or `last30d`) |
| `30 Days 95th` | 95th percentile total bandwidth in Mbps |
| `30 Days P95 Peak` | Peak P95 bandwidth in Mbps |

#### Specifying an output directory

```bash
uv run python decrypt_metrics.py vco116.combined.csv /path/to/output
```

Per-month CSV files are written into the specified directory.

### Auto-Detection

The script automatically detects the input format:

- If the file is a valid zip archive → treated as an encrypted archive
- Otherwise → treated as a combined CSV

No flags or format hints are needed.

## Output Files

### From an encrypted archive

| Input | Output | Description |
|-------|--------|-------------|
| `export.zip` | `export/*.csv` | Original per-month CSV files extracted from the encrypted payload |

### From a combined CSV

| Input | Output | Description |
|-------|--------|-------------|
| `vco116.combined.csv` | `vco116.combined/vco116.{MM-YYYY}.csv` | One CSV per month with decoded metric columns |

Per-month CSV files are written with UTF-8 BOM encoding (`utf-8-sig`), matching the encoding used by `vco_edge_export`.

## CLI Reference

```
python decrypt_metrics.py <input-path> [output-dir]

Arguments:
  input-path    Path to an encrypted zip archive or a combined CSV file
  output-dir    Optional output directory (defaults to a directory named
                after the input file's stem, in the input file's parent)
```

## Error Handling

| Condition | Behavior |
|-----------|----------|
| Input file does not exist | Prints error and exits with code 1 |
| Zip archive has no `data.enc` member | Prints error indicating invalid archive format |
| Decryption fails (corrupt or incompatible archive) | Prints decryption error and exits with code 1 |
| Corrupt or invalid zip structure | Prints bad-zip error and exits with code 1 |
| Combined CSV missing required columns (`Edge UUID`, `Record Hash`) | Prints error naming the missing columns |
| Individual row decoding fails | Logs a warning and continues with remaining rows |
| Output directory cannot be created | Prints OS error and exits with code 1 |
