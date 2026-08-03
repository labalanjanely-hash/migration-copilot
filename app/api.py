from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException

from app.config import get_settings
from app.storage import SQLiteAuditRepository

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {"status": "ok", "service": settings.app_name, "read_only": True}


@app.get("/v1/capabilities")
def capabilities() -> dict[str, Any]:
    return {
        "status": "read_only_mvp",
        "external_connections": {"kajabi": False, "gohighlevel": False},
        "implemented_engines": ["ingestion", "normalization", "duplicates",
                                "entitlements", "risks", "reports", "advisor"],
        "release_status": "NO_GO",
    }


@app.get("/v1/runs/{run_id}")
def run_summary(run_id: str) -> dict[str, Any]:
    prefix = "sqlite:///"
    if not settings.database_url.startswith(prefix):
        raise HTTPException(503, "Only local SQLite is enabled.")
    result = SQLiteAuditRepository(Path(settings.database_url.removeprefix(prefix))).get(run_id)
    if result is None:
        raise HTTPException(404, "Run not found.")
    return {
        "run_id": result.run_id, "release_status": result.release_status,
        "sources": len(result.source_manifests), "records": len(result.normalized_records),
        "duplicates": len(result.duplicate_decisions),
        "entitlements": len(result.entitlement_decisions), "risks": len(result.risks),
        "candidate_rows": len(result.prepared_dataset.rows),
        "activation_authorized": False,
    }

