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

### Default run

```bash
./vco_edge_export
```

### Federal VCO

For federal VCO instances, add the `--federal` flag to strip personally identifiable information (PII) from the output:

```bash
./vco_edge_export --federal
```

---

## CLI Reference

```
./vco_edge_export [OPTIONS]

Options:
  -v, --version            Print version and exit
  --vco-host HOST          VCO hostname (overrides VCO_HOST in .env)
  --vco-token TOKEN        VCO API token (overrides VCO_TOKEN in .env)
  --federal                Strip PII from output (for federal VCO instances)
```
