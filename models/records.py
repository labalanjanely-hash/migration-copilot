from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExportType(StrEnum):
    CONTACTS = "contacts"
    TRANSACTIONS = "transactions"
    SUBSCRIPTIONS = "subscriptions"
    PAYMENT_PLANS = "payment_plans"
    OFFER_PURCHASES = "offer_purchases"
    PRODUCT_ACCESS = "product_access"
    COMMUNITY_MEMBERSHIPS = "community_memberships"
    REFUNDS = "refunds"
    DISPUTES = "disputes"
    OTHER = "other"


class IssueSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class SourceRecord(BaseModel):
    model_config = ConfigDict(frozen=True)
    source_file: str
    source_row: int = Field(ge=1)
    record_type: str
    values: dict[str, Any]


class IngestionRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    path: Path
    export_type: ExportType
    required_columns: tuple[str, ...] = ()
    expected_columns: tuple[str, ...] = ()
    encoding: str | None = None


class ValidationIssue(BaseModel):
    model_config = ConfigDict(frozen=True)
    severity: IssueSeverity
    code: str
    message: str
    source_file: str
    source_row: int | None = Field(default=None, ge=1)
    source_field: str | None = None


class QuarantinedRow(BaseModel):
    model_config = ConfigDict(frozen=True)
    source_file: str
    source_row: int = Field(ge=1)
    reason_codes: tuple[str, ...] = Field(min_length=1)


class SourceManifest(BaseModel):
    model_config = ConfigDict(frozen=True)
    source_file: str
    absolute_path: Path
    export_type: ExportType
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(ge=0)
    encoding: str
    delimiter: str = Field(min_length=1, max_length=1)
    columns: tuple[str, ...]
    rows_seen: int = Field(ge=0)
    rows_accepted: int = Field(ge=0)
    rows_quarantined: int = Field(ge=0)


class FileIngestionResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    manifest: SourceManifest | None
    records: tuple[SourceRecord, ...] = ()
    issues: tuple[ValidationIssue, ...] = ()
    quarantined_rows: tuple[QuarantinedRow, ...] = ()

    @property
    def is_valid(self) -> bool:
        return self.manifest is not None and not any(
            issue.severity is IssueSeverity.ERROR for issue in self.issues
        )


class BatchIngestionResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    files: tuple[FileIngestionResult, ...]

    @property
    def is_valid(self) -> bool:
        return bool(self.files) and all(item.is_valid for item in self.files)

