from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from models.decisions import Decision
from models.evidence import Evidence
from models.records import SourceManifest


class RiskSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class NormalizedRecord(BaseModel):
    model_config = ConfigDict(frozen=True)
    source_file: str
    source_row: int
    record_type: str
    normalized_email: str | None = None
    normalized_phone: str | None = None
    normalized_name: str | None = None
    values: dict[str, Any]
    evidence: tuple[Evidence, ...] = Field(min_length=1)


class RiskFinding(BaseModel):
    model_config = ConfigDict(frozen=True)
    code: str
    severity: RiskSeverity
    subject_id: str
    summary: str
    recommended_action: str
    blocks_activation: bool = True
    evidence: tuple[Evidence, ...] = Field(min_length=1)


class PreparedDataset(BaseModel):
    model_config = ConfigDict(frozen=True)
    rows: tuple[dict[str, Any], ...]
    contact_rows: tuple[dict[str, Any], ...] = ()
    manual_review_rows: tuple[dict[str, Any], ...] = ()
    excluded_decisions: tuple[Decision, ...]


class PreparationInput(BaseModel):
    model_config = ConfigDict(frozen=True)
    records: tuple[NormalizedRecord, ...]
    duplicate_decisions: tuple[Decision, ...]
    entitlement_decisions: tuple[Decision, ...]
    identity_record_types: tuple[str, ...]


class RiskInput(BaseModel):
    model_config = ConfigDict(frozen=True)
    records: tuple[NormalizedRecord, ...]
    duplicate_decisions: tuple[Decision, ...]
    entitlement_decisions: tuple[Decision, ...]


class PipelineResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    run_id: str
    source_manifests: tuple[SourceManifest, ...]
    normalized_records: tuple[NormalizedRecord, ...]
    duplicate_decisions: tuple[Decision, ...]
    entitlement_decisions: tuple[Decision, ...]
    risks: tuple[RiskFinding, ...]
    prepared_dataset: PreparedDataset
    release_status: str
