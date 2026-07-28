# VCO On-Prem Data Export

Python scripts that export data from VMware VeloCloud Orchestrator (VCO) on-premises instances via JSON-RPC 2.0 API.

## Scripts

### `vco_edge_export.py`

Merges the VCO network-wide license CSV export with per-enterprise edge status data. Outputs a single CSV file with license details enriched by edge state and UUID.

```bash
uv run python vco_edge_export.py    # → vco_edge_export.csv
```

### `get_all_users.py`

Audits all enterprise and partner/operator users across the VCO. Outputs a styled 3-sheet Excel workbook (Summary, Enterprise Users, Partner Users) with role badges, auto-filters, and frozen panes.

```bash
uv run python get_all_users.py      # → vco_user_audit.xlsx
```

## Setup

### Prerequisites

- Python 3.13+
- [`uv`](https://docs.astral.sh/uv/) package manager
- Network access to a VCO on-premises instance
- Valid VCO API token

### Install `uv`

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

For other methods (Homebrew, pip, Windows), see the [uv installation docs](https://docs.astral.sh/uv/getting-started/installation/).

### Install dependencies

```bash
uv sync
```

### Configuration

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env` with your VCO credentials:

```
VCO_URL=https://<vco-host>/portal/
VCO_TOKEN=<your-api-token>
```

The token can be provided with or without the `Token ` prefix — the script normalizes it automatically.

> **Note:** SSL verification is disabled (`verify=False`) since on-prem VCO instances typically use self-signed certificates.

## Error Handling

Both scripts validate configuration at startup and fail fast on authentication errors:

- **Missing env vars** — prints which variable is missing and exits
- **Invalid/expired token** — detects HTTP 401/403 and JSON-RPC error responses, exits with a clear message pointing to the token
- **Empty enterprise list** — treated as a likely auth failure with guidance to check credentials
- **Rate limiting** — automatic retry with backoff on HTTP 429 (up to 5 attempts)

## VCO API Methods Used

| Method | Purpose |
|--------|---------|
| `network/getNetworkEnterprises` | List all enterprises |
| `enterprise/getEnterprise` | Enterprise and partner details |
| `enterprise/getEnterpriseEdgeList` | Edge devices with site/HA/config/links |
| `license/exportNetworkEdgeLicenseData` | Network-wide license CSV export |
| `enterprise/getEnterpriseUsers` | Users per enterprise |
| `network/getNetworkOperatorUsers` | Partner-level users |
