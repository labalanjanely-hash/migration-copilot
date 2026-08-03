from pathlib import Path

import pytest
from pydantic import ValidationError

from app.services.pipeline import MigrationPipeline
from app.storage import SQLiteAuditRepository
from engines.ingestion import CsvIngestionEngine
from models.decisions import Decision, DecisionStatus
from models.evidence import Evidence, EvidenceType
from models.records import ExportType, IngestionRequest
from reports.bundle import ReportBundleWriter
from reports.source_register import SourceRegisterWriter
from rules.configuration import PipelineConfiguration, SourceFieldMap


def config() -> PipelineConfiguration:
    return PipelineConfiguration(
        version="test",
        fields_by_record_type={
            "contacts": SourceFieldMap(email="Email", name="Name"),
            "transactions": SourceFieldMap(email="Email", status="Status", offer_id="Offer ID"),
            "product_access": SourceFieldMap(email="Email", product_id="Product ID"),
        },
    )


def evidence() -> Evidence:
    return Evidence(evidence_type=EvidenceType.TRANSACTION, source_file="transactions.csv",
                    source_row=2, source_field="Status", raw_value="succeeded")


def sources(tmp_path: Path, status: str = "succeeded") -> list[IngestionRequest]:
    contacts = tmp_path / "contacts.csv"
    transactions = tmp_path / "transactions.csv"
    contacts.write_text("Email,Name\nroyce@example.com,Royce\n", encoding="utf-8")
    transactions.write_text(
        f"Email,Status,Offer ID\nROYCE@example.com ,{status},offer-1\n", encoding="utf-8"
    )
    return [
        IngestionRequest(path=contacts, export_type=ExportType.CONTACTS,
                         required_columns=("Email", "Name")),
        IngestionRequest(path=transactions, export_type=ExportType.TRANSACTIONS,
                         required_columns=("Email", "Status", "Offer ID")),
    ]


def test_decision_requires_evidence() -> None:
    with pytest.raises(ValidationError):
        Decision(subject_id="x", decision_type="entitlement", status=DecisionStatus.VERIFIED,
                 rationale="x", evidence=())


def test_conflict_requires_manual_review() -> None:
    with pytest.raises(ValidationError):
        Decision(subject_id="x", decision_type="entitlement", status=DecisionStatus.VERIFIED,
                 rationale="x", evidence=(evidence(),), conflicts=("refund",))


def test_ingestion_quarantines_malformed_row_without_pii(tmp_path) -> None:
    source = tmp_path / "contacts.csv"
    source.write_text("Email,Name\na@example.com,A,extra\n", encoding="utf-8")
    result = CsvIngestionEngine().execute([
        IngestionRequest(path=source, export_type=ExportType.CONTACTS)
    ])
    assert result.files[0].manifest is not None
    assert result.files[0].manifest.rows_quarantined == 1
    output = SourceRegisterWriter().write(result, tmp_path / "register.json")
    assert "a@example.com" not in output.read_text(encoding="utf-8")


def test_succeeded_purchase_creates_non_authorized_candidate(tmp_path) -> None:
    result = MigrationPipeline(config()).run(sources(tmp_path))
    assert result.release_status == "NO_GO"
    assert result.entitlement_decisions[0].status is DecisionStatus.VERIFIED
    assert result.prepared_dataset.rows[0]["Activation Authorized"] is False


def test_refund_conflict_requires_review(tmp_path) -> None:
    requests = sources(tmp_path)
    requests[1].path.write_text(
        "Email,Status,Offer ID\nroyce@example.com,succeeded,offer-1\n"
        "royce@example.com,refunded,offer-1\n", encoding="utf-8"
    )
    result = MigrationPipeline(config()).run(requests)
    assert result.entitlement_decisions[0].status is DecisionStatus.MANUAL_REVIEW
    assert not result.prepared_dataset.rows
    assert result.risks[0].severity.value == "critical"


def test_product_access_alone_requires_review(tmp_path) -> None:
    source = tmp_path / "access.csv"
    source.write_text("Email,Product ID\nroyce@example.com,p1\n", encoding="utf-8")
    result = MigrationPipeline(config()).run([
        IngestionRequest(path=source, export_type=ExportType.PRODUCT_ACCESS,
                         required_columns=("Email", "Product ID"))
    ])
    assert result.entitlement_decisions[0].status is DecisionStatus.MANUAL_REVIEW


def test_persistence_and_reports(tmp_path) -> None:
    result = MigrationPipeline(config()).run(sources(tmp_path))
    repository = SQLiteAuditRepository(tmp_path / "audit.db")
    repository.save(result)
    assert repository.get(result.run_id) == result
    paths = ReportBundleWriter().write(result, tmp_path / "outputs")
    assert len(paths) == 3 and all(path.stat().st_size > 0 for path in paths)

