# Architecture

Dependency direction is interfaces → deterministic engines → immutable domain models.
FastAPI, Typer, SQLite, XLSX, and OpenAI are outer adapters. Exact source mappings are
configuration, never guesses. Every decision contains source-file, row, and field
evidence. Conflicts force manual review. Product access alone never creates verified
entitlement. Dataset preparation includes verified purchase decisions only and still
sets `Activation Authorized` to false. Every MVP run is permanently `NO_GO`.

The Agents SDK advisor has one read-only tool over an exact saved run ID. It cannot
access arbitrary files, mutate SQLite, connect to Kajabi or GHL, or override the
deterministic engines.

