# VCO Edge Export — Usage & Build Guide

## Table of Contents

- [Usage Guide](#usage-guide)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Configuration](#configuration)
  - [Running the Script](#running-the-script)
  - [CLI Reference](#cli-reference)
  - [Output Files](#output-files)
  - [Error Handling](#error-handling)
- [Building a Self-Contained Binary](#building-a-self-contained-binary)
  - [PyInstaller](#pyinstaller)
  - [Nuitka](#nuitka)
  - [Common Notes](#common-notes)

---

## Usage Guide

### Prerequisites

- Python 3.13+
- [`uv`](https://docs.astral.sh/uv/) package manager
- Network access to a VCO on-premises instance
- Valid VCO API token

#### Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

For other methods (Homebrew, pip, Windows), see the [uv installation docs](https://docs.astral.sh/uv/getting-started/installation/).

### Installation

Clone the repository, then install all dependencies:

```bash
uv sync
```

### Configuration

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```
VCO_HOST=<vco-hostname>
VCO_TOKEN=eyJhbGciOi...
```

- **VCO_HOST** is the VCO hostname only (e.g. `veco12-kiad1.velocloud.net`). Defaults to `localhost` if not set. The script constructs the full URL (`https://<host>/portal/`) automatically.
- **VCO_TOKEN** is the raw API token value. Do not include the `Token ` prefix — the script adds it automatically.

Both values can also be supplied via CLI flags (`--vco-host`, `--vco-token`), which override the `.env` values.

> **Note:** SSL verification is disabled (`verify=False`) because on-prem VCO instances typically use self-signed certificates.

### Running the Script

#### Basic export

Merges the VCO network-wide license CSV with per-enterprise edge status, and collects 95th percentile bandwidth metrics for the last 3 complete calendar months (default):

```bash
uv run python vco_edge_export.py
```

This produces `vco_edge_export.csv` plus per-month metrics CSV files and a `.zip` archive.

#### Customizing the time range

```bash
# Last 1 complete calendar month
uv run python vco_edge_export.py --months 1

# Last 6 complete calendar months
uv run python vco_edge_export.py --months 6

# Trailing 30 days (including today) instead of calendar months
uv run python vco_edge_export.py --last_30_days
```

#### Skipping 95th percentile collection

Set the `SKIP_95TH` environment variable to disable metrics collection entirely:

```bash
SKIP_95TH=1 uv run python vco_edge_export.py
```

This produces only the basic `vco_edge_export.csv` without any metrics files.

#### CLI overrides for credentials

Override `.env` values directly from the command line:

```bash
uv run python vco_edge_export.py --vco-host veco12-kiad1.velocloud.net --vco-token "eyJhbGciOi..."
```

#### Diagnose a specific edge

Print detailed diagnostics (sample counts, null/zero prevalence, daily P95 values, monthly calculations) for a single edge and exit:

```bash
uv run python vco_edge_export.py --diagnose "edge-name"
```

This is useful for troubleshooting when an edge's metrics look wrong or are missing.

#### Strict sample validation

By default, sample count mismatches are logged as warnings. To abort on mismatch instead:

```bash
uv run python vco_edge_export.py --strict_validation
```

### CLI Reference

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--vco-host` | string | `localhost` | VCO hostname (e.g. `veco12-kiad1.velocloud.net`). Overrides `VCO_HOST` in `.env` |
| `--vco-token` | string | `.env` | VCO API token. Overrides `VCO_TOKEN` in `.env` |
| `--months N` | int | `3` | Number of complete calendar months to collect (1–12). Mutually exclusive with `--last_30_days` |
| `--last_30_days` | boolean | `False` | Collect metrics for the trailing 30 days instead of complete calendar months. Mutually exclusive with `--months` |
| `--all_metrics` | boolean | `False` | Include tx and rx columns in addition to total in the output CSVs. By default only the `30 Days 95th` (total) column is included |
| `--strict_validation` | boolean | `False` | Abort on sample count mismatch instead of logging a warning |
| `--diagnose EDGE_NAME` | string | `None` | Troubleshoot metrics for a specific edge by name. Prints diagnostic output and exits |

| Environment Variable | Description |
|---------------------|-------------|
| `VCO_HOST` | VCO hostname, defaults to `localhost` (overridden by `--vco-host`) |
| `VCO_TOKEN` | VCO API token (overridden by `--vco-token`) |
| `SKIP_95TH` | Set to `1` to disable 95th percentile metrics collection |

### Output Files

| Condition | Output | Description |
|-----------|--------|-------------|
| Always | `vco_edge_export.csv` | License data merged with edge status (Edge UUID, Edge Status columns) |
| 95th enabled (default) | `<vco-host>_metrics_<timestamp>/` | Directory containing per-month CSV files with P95 bandwidth columns |
| 95th enabled (default) | `<vco-host>_metrics_<timestamp>.zip` | Zip archive of the above directory |
| `--diagnose` | *(stdout only)* | Diagnostic report printed to the terminal; no files written |

The per-month CSV files include a `30 Days 95th` column (total P95 bandwidth in Mbps) by default. Use `--all_metrics` to also include the tx and rx columns (`30 Days Tx 95th`, `30 Days Rx 95th`).

### Error Handling

| Condition | Behavior |
|-----------|----------|
| Missing `VCO_TOKEN` | Prints an error and exits immediately |
| Invalid or expired API token | Detects HTTP 401/403 and JSON-RPC auth errors; exits with a message pointing to the token |
| Empty enterprise list | Treated as likely auth failure; prints guidance to check credentials |
| HTTP 429 rate limiting | Automatic retry with backoff (up to 5 attempts, respects `Retry-After` header) |
| `--months` outside 1–12 | Prints an error and exits |

---

## Building a Self-Contained Binary

A self-contained binary bundles Python, all dependencies, and the application code (`vco_edge_export.py`, `metrics.py`, `output.py`) into a single executable. This lets you distribute and run the tool on machines that don't have Python or `uv` installed.

The project includes a `Makefile` that auto-detects all imports and generates the correct build flags for either tool.

### PyInstaller

PyInstaller is already included as a dev dependency.

#### Build

```bash
make pyinstaller
```

This will:
1. Run `uv sync` to ensure dependencies are installed
2. Install `pyinstaller` as a dev dependency if not already present
3. Auto-detect all local and third-party imports from the script
4. Build a single-file binary

#### Output

```
dist/vco_edge_export          # macOS / Linux
dist/vco_edge_export.exe      # Windows
```

PyInstaller also creates a `build/` directory and a `vco_edge_export.spec` file. These are build artifacts and can be cleaned up with `make clean`.

### Nuitka

[Nuitka](https://nuitka.net/) compiles Python to C and produces optimized native binaries. It generally produces smaller binaries with faster startup compared to PyInstaller, at the cost of longer build times.

Nuitka requires a C compiler on the build machine:

- **macOS:** Xcode Command Line Tools (`xcode-select --install`)
- **Linux:** `gcc` or `clang` (e.g. `apt install gcc`)
- **Windows:** Visual Studio Build Tools or MinGW

#### Build

```bash
make nuitka
```

This will:
1. Run `uv sync` to ensure dependencies are installed
2. Install `nuitka` as a dev dependency if not already present
3. Auto-detect all local and third-party imports from the script
4. Compile to C and build a single-file binary

#### Output

```
vco_edge_export.bin           # Linux
vco_edge_export.exe           # Windows
vco_edge_export.app           # macOS (or .bin depending on Nuitka version)
```

### Cleaning Build Artifacts

```bash
make clean
```

Removes all build artifacts from both PyInstaller (`build/`, `dist/`, `*.spec`) and Nuitka (`*.build/`, `*.dist/`, `*.onefile-build/`).

### Common Notes

**The `.env` file is not bundled into the binary.** It must be present in the working directory when you run the binary, or you must pass `--vco-host` and `--vco-token` on the command line.

**Build on the target platform.** A binary built on macOS will not run on Linux or Windows, and vice versa. Build on the same OS (and architecture) where you intend to run it.

**Local modules are bundled automatically.** The Makefile's import detection walks the full import tree from the main script and includes all local modules (`metrics.py`, `output.py`) and third-party packages.

**Binary size.** Expect roughly 30–80 MB depending on the tool and platform, since pandas and its transitive dependencies are substantial.

### PyInstaller vs Nuitka Comparison

| | PyInstaller | Nuitka |
|---|---|---|
| Already in dev deps | Yes | No (auto-installed by `make nuitka`) |
| Build time | Fast (seconds) | Slow (minutes — compiles to C) |
| Binary size | Larger | Smaller |
| Startup time | Slower (unpacks to temp dir) | Faster (native execution) |
| C compiler required | No | Yes |
| Cross-platform | Build per platform | Build per platform |
