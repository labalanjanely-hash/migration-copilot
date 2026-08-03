# Migration Copilot

Production-oriented, read-only Kajabi to GoHighLevel migration analysis. The MVP reads
local CSV exports, preserves evidence, normalizes identities, flags duplicates, builds
a conservative Entitlement Ledger, detects risks, saves SQLite audit snapshots, creates
XLSX/CSV/JSON reports, and offers an optional OpenAI Agents SDK review.

## Safety boundary

- No Kajabi or GoHighLevel connection or mutation.
- No browser automation and no non-OpenAI API calls.
- Product access never proves purchase or entitlement.
- Conflicts and uncertain records always route to manual review.
- Candidate rows never authorize activation; every run remains `NO_GO`.

## Install and verify

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
ruff check .
mypy app engines models tools rules reports
```

## Inspect sources

```bash
migration-copilot inspect-csv contacts.csv --export-type contacts \
  --required-column Email --output outputs/source-register.json
```

## Run deterministic pipeline

Review the example config and replace every field mapping with verified exact headers.

```bash
migration-copilot run-pipeline \
  --source contacts=/absolute/path/contacts.csv \
  --source transactions=/absolute/path/transactions.csv \
  --configuration docs/pipeline-config.example.json \
  --output-directory outputs --database migration_copilot.db
```

## Optional OpenAI review

```bash
migration-copilot advise --run-id RUN_ID --database migration_copilot.db
```

Only `advise` calls OpenAI. API billing is separate from ChatGPT subscriptions. The
current project key previously reached OpenAI but returned `insufficient_quota`; restore
API credits before expecting a live advisory response.

See [docs/architecture.md](docs/architecture.md).

