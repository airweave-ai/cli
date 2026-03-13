# Airweave CLI

[![pypi](https://img.shields.io/pypi/v/airweave-cli)](https://pypi.python.org/pypi/airweave-cli)
[![npm](https://img.shields.io/npm/v/@airweave/cli)](https://www.npmjs.com/package/@airweave/cli)

A command-line interface for [Airweave](https://airweave.ai). Search across your connected sources from any terminal. Built for developers and AI agents.

## Installation

```sh
pip install airweave-cli
```

This installs the `airweave` binary.

## Quick Start

```sh
# Set your API key
export AIRWEAVE_API_KEY="your-api-key"

# Search a collection
airweave search "quarterly revenue figures" --collection finance-data

# List collections
airweave collections list
```

## Authentication

The CLI resolves credentials in this order:

1. `AIRWEAVE_API_KEY` environment variable
2. `~/.airweave/config.json` (saved via `airweave auth login`)

For interactive setup:

```sh
airweave auth login
```

This prompts for your API key, validates it, and saves it locally.

### Self-hosted

Point the CLI at your own Airweave instance:

```sh
export AIRWEAVE_BASE_URL="https://airweave.internal.corp.com"
```

Or set it during `airweave auth login`.

## Commands

### Search

```sh
airweave search "<query>" --collection <id> --top-k 5 --format json
```

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--collection` | `-c` | `$AIRWEAVE_COLLECTION` | Collection readable ID |
| `--top-k` | `-k` | `10` | Number of results |
| `--format` | `-f` | `json` | Output format: `json` or `text` |

JSON output (default) writes pure JSON to stdout — nothing else. Pipe it:

```sh
airweave search "query" -c my-collection | jq '.results[0].md_content'
```

### Auth

```sh
airweave auth login     # interactive setup
airweave auth status    # show current auth state
airweave auth logout    # clear saved credentials
```

### Collections

```sh
airweave collections list                           # list all
airweave collections create --name "My Data"        # create
airweave collections get my-data-x7k9m              # get details
```

### Sources

```sh
airweave sources list --collection my-data          # list source connections
airweave sources sync <source-connection-id>        # trigger sync
airweave sources sync <id> --force                  # full re-sync
```

## Agent Usage

The CLI is designed for non-interactive use by AI agents. Every command:

- Outputs clean JSON to stdout (default)
- Sends all errors to stderr
- Uses correct exit codes (0 = success, 1 = error)

### Environment variables

```sh
export AIRWEAVE_API_KEY="sk-..."
export AIRWEAVE_COLLECTION="my-knowledge-base"
export AIRWEAVE_BASE_URL="https://api.airweave.ai"  # optional
```

### Piping

```sh
# Get the top result's content
airweave search "how to reset password" | jq -r '.results[0].md_content'

# Get the AI-generated answer
airweave search "what is our refund policy" | jq -r '.completion'

# List collection IDs
airweave collections list | jq -r '.[].readable_id'
```

### CI / Cloud Functions

```yaml
# GitHub Actions example
- name: Search Airweave
  env:
    AIRWEAVE_API_KEY: ${{ secrets.AIRWEAVE_API_KEY }}
    AIRWEAVE_COLLECTION: docs
  run: |
    result=$(airweave search "deployment guide")
    echo "$result" | jq '.results[:3]'
```

No SDK imports, no MCP server, no config files — just an env var and a shell.

## Configuration

Config file location: `~/.airweave/config.json`

```json
{
  "api_key": "sk-...",
  "base_url": "https://api.airweave.ai",
  "collection": "my-default-collection"
}
```

Resolution order for all settings:

1. CLI flag (e.g. `--collection`)
2. Environment variable (e.g. `AIRWEAVE_COLLECTION`)
3. Config file
4. Default / error

## Contributing

```sh
git clone https://github.com/airweave-ai/cli.git
cd cli
poetry install
poetry run airweave --help
```
