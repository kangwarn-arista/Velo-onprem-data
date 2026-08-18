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
VCO_URL=https://<vco-host>/portal/
VCO_TOKEN=<your-api-token>
```

- **VCO_URL** must point to the VCO portal endpoint (a trailing `/` is added automatically if missing).
- **VCO_TOKEN** can be provided with or without the `Token ` prefix — the script normalizes it automatically.

> **Note:** SSL verification is disabled (`verify=False`) because on-prem VCO instances typically use self-signed certificates.

### Running the Script

#### Basic export

Merges the VCO network-wide license CSV with per-enterprise edge status:

```bash
uv run python vco_edge_export.py
```

This produces `vco_edge_export.csv` in the current directory.

#### 95th percentile bandwidth metrics

Collect per-edge-link 95th percentile bandwidth metrics for one or more months:

```bash
# Last 1 complete calendar month (default)
uv run python vco_edge_export.py --collect_95th

# Last 3 complete calendar months
uv run python vco_edge_export.py --collect_95th --months 3

# Trailing 30 days (including today) instead of calendar months
uv run python vco_edge_export.py --collect_95th --last_30_days
```

When `--collect_95th` is enabled, the script also produces per-month CSV files and a `.zip` archive (see [Output Files](#output-files)).

#### Diagnose a specific edge

Print detailed diagnostics (sample counts, null/zero prevalence, daily P95 values, monthly calculations) for a single edge and exit:

```bash
uv run python vco_edge_export.py --collect_95th --diagnose "edge-name"
```

This is useful for troubleshooting when an edge's metrics look wrong or are missing.

#### Strict sample validation

By default, sample count mismatches are logged as warnings. To abort on mismatch instead:

```bash
uv run python vco_edge_export.py --collect_95th --strict_validation
```

### CLI Reference

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--collect_95th` | boolean | `False` | Enable 95th percentile bandwidth metrics collection per edge link |
| `--months N` | int | `1` | Number of complete calendar months to collect (1–12). Mutually exclusive with `--last_30_days` |
| `--last_30_days` | boolean | `False` | Collect metrics for the trailing 30 days instead of complete calendar months. Mutually exclusive with `--months` |
| `--strict_validation` | boolean | `False` | Abort on sample count mismatch instead of logging a warning |
| `--diagnose EDGE_NAME` | string | `None` | Troubleshoot metrics for a specific edge by name. Prints diagnostic output and exits |

### Output Files

| Mode | Output | Description |
|------|--------|-------------|
| Basic (no flags) | `vco_edge_export.csv` | License data merged with edge status (Edge UUID, Edge Status columns) |
| `--collect_95th` | `vco_edge_export.csv` | Same as basic |
| `--collect_95th` | `<vco-name>_metrics_<timestamp>/` | Directory containing per-month CSV files with 95th percentile, max, and avg bandwidth columns |
| `--collect_95th` | `<vco-name>_metrics_<timestamp>.zip` | Zip archive of the above directory |
| `--diagnose` | *(stdout only)* | Diagnostic report printed to the terminal; no files written |

The per-month CSV files include columns for P95, max, and avg bandwidth in Mbps for tx, rx, and total directions.

### Error Handling

| Condition | Behavior |
|-----------|----------|
| Missing `VCO_TOKEN` or `VCO_URL` | Prints an error and exits immediately |
| Invalid or expired API token | Detects HTTP 401/403 and JSON-RPC auth errors; exits with a message pointing to the token |
| Empty enterprise list | Treated as likely auth failure; prints guidance to check credentials |
| HTTP 429 rate limiting | Automatic retry with backoff (up to 5 attempts, respects `Retry-After` header) |
| `--months` outside 1–12 | Prints an error and exits |

---

## Building a Self-Contained Binary

A self-contained binary bundles Python, all dependencies, and the application code (`vco_edge_export.py`, `metrics.py`, `output.py`) into a single executable. This lets you distribute and run the tool on machines that don't have Python or `uv` installed.

### PyInstaller

PyInstaller is already included as a dev dependency.

#### Install

```bash
uv sync
```

This pulls in `pyinstaller` from the dev dependency group.

#### Build

```bash
uv run pyinstaller --onefile \
  --hidden-import=dotenv \
  --hidden-import=requests \
  --hidden-import=pandas \
  --hidden-import=urllib3 \
  vco_edge_export.py
```

The `--hidden-import` flags ensure dynamic imports are included in the bundle.

#### Output

The binary is created at:

```
dist/vco_edge_export          # macOS / Linux
dist/vco_edge_export.exe      # Windows
```

PyInstaller also creates a `build/` directory and a `vco_edge_export.spec` file. These are build artifacts and can be safely deleted or added to `.gitignore`.

#### Run

```bash
./dist/vco_edge_export --collect_95th --months 3
```

All CLI flags work identically to the Python version.

### Nuitka

[Nuitka](https://nuitka.net/) compiles Python to C and produces optimized native binaries. It generally produces smaller binaries with faster startup compared to PyInstaller, at the cost of longer build times.

#### Install

```bash
uv add --dev nuitka
```

Nuitka also requires a C compiler on the build machine:

- **macOS:** Xcode Command Line Tools (`xcode-select --install`)
- **Linux:** `gcc` or `clang` (e.g. `apt install gcc`)
- **Windows:** Visual Studio Build Tools or MinGW

#### Build

```bash
uv run python -m nuitka \
  --standalone \
  --onefile \
  --include-module=dotenv \
  --include-module=requests \
  --include-module=pandas \
  --include-module=urllib3 \
  vco_edge_export.py
```

#### Output

The binary is created at:

```
vco_edge_export.bin           # Linux
vco_edge_export.exe           # Windows
vco_edge_export.app           # macOS (or .bin depending on Nuitka version)
```

#### Run

```bash
./vco_edge_export.bin --collect_95th --months 3
```

### Common Notes

**The `.env` file is not bundled into the binary.** It must be present in the working directory when you run the binary, just like when running the Python script directly. Copy `.env.example` alongside the binary and fill in your values.

**Build on the target platform.** A binary built on macOS will not run on Linux or Windows, and vice versa. Build on the same OS (and architecture) where you intend to run it.

**Local modules are bundled automatically.** Both PyInstaller and Nuitka detect that `vco_edge_export.py` imports `metrics.py` and `output.py` and include them in the binary.

**Binary size.** Expect roughly 30–80 MB depending on the tool and platform, since pandas and its transitive dependencies are substantial.

### PyInstaller vs Nuitka Comparison

| | PyInstaller | Nuitka |
|---|---|---|
| Already in dev deps | Yes | No (needs `uv add --dev nuitka`) |
| Build time | Fast (seconds) | Slow (minutes — compiles to C) |
| Binary size | Larger | Smaller |
| Startup time | Slower (unpacks to temp dir) | Faster (native execution) |
| C compiler required | No | Yes |
| Cross-platform | Build per platform | Build per platform |
