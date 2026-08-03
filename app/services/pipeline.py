from uuid import uuid4

from engines.dataset_preparation import DatasetPreparationEngine
from engines.duplicate_detection import DuplicateDetectionEngine
from engines.entitlement_ledger import EntitlementLedgerEngine
from engines.ingestion import CsvIngestionEngine
from engines.normalization import NormalizationEngine
from engines.risk_detection import RiskDetectionEngine
from models.migration import PipelineResult, RiskInput
from models.records import IngestionRequest, IssueSeverity
from rules.configuration import PipelineConfiguration


class PipelineValidationError(ValueError):
    pass


class MigrationPipeline:
    def __init__(self, configuration: PipelineConfiguration) -> None:
        self._config = configuration

    def run(self, requests: list[IngestionRequest]) -> PipelineResult:
        if not requests:
            raise PipelineValidationError("At least one source is required.")
        ingestion = CsvIngestionEngine().execute(requests)
        errors = [issue for result in ingestion.files for issue in result.issues
                  if issue.severity is IssueSeverity.ERROR]
        if errors:
            raise PipelineValidationError(
                "Source validation failed: " + ", ".join(sorted({item.code for item in errors}))
            )
        records = [record for result in ingestion.files for record in result.records]
        normalized = NormalizationEngine(self._config).execute(records)
        duplicates = DuplicateDetectionEngine(self._config.identity_record_types).execute(
            normalized
        )
        entitlements = EntitlementLedgerEngine(self._config).execute(normalized)
        risks = RiskDetectionEngine().execute([RiskInput(
            records=tuple(normalized), duplicate_decisions=tuple(duplicates),
            entitlement_decisions=tuple(entitlements),
        )])
        manifests = tuple(item.manifest for item in ingestion.files if item.manifest is not None)
        return PipelineResult(
            run_id=str(uuid4()), source_manifests=manifests,
            normalized_records=tuple(normalized), duplicate_decisions=tuple(duplicates),
            entitlement_decisions=tuple(entitlements), risks=tuple(risks),
            prepared_dataset=DatasetPreparationEngine().execute(entitlements),
            release_status="NO_GO",
        )
