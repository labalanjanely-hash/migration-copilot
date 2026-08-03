import json
import sqlite3
from pathlib import Path

from models.migration import PipelineResult


class SQLiteAuditRepository:
    def __init__(self, path: Path) -> None:
        self._path = path.expanduser()

    def initialize(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS pipeline_runs "
                "(run_id TEXT PRIMARY KEY, release_status TEXT NOT NULL, "
                "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, payload_json TEXT NOT NULL)"
            )

    def save(self, result: PipelineResult) -> None:
        self.initialize()
        payload = json.dumps(result.model_dump(mode="json"), separators=(",", ":"))
        with sqlite3.connect(self._path) as connection:
            connection.execute(
                "INSERT INTO pipeline_runs (run_id, release_status, payload_json) VALUES (?, ?, ?)",
                (result.run_id, result.release_status, payload),
            )

    def get(self, run_id: str) -> PipelineResult | None:
        self.initialize()
        with sqlite3.connect(self._path) as connection:
            row = connection.execute(
                "SELECT payload_json FROM pipeline_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return PipelineResult.model_validate_json(row[0]) if row else None

