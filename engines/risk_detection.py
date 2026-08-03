from collections.abc import Sequence

from engines.base import Engine
from models.decisions import DecisionStatus
from models.migration import RiskFinding, RiskInput, RiskSeverity


class RiskDetectionEngine(Engine[RiskInput, list[RiskFinding]]):
    def execute(self, items: Sequence[RiskInput]) -> list[RiskFinding]:
        findings: list[RiskFinding] = []
        for item in items:
            for record in item.records:
                if not record.normalized_email or "@" not in record.normalized_email:
                    findings.append(RiskFinding(
                        code="MISSING_OR_INVALID_EMAIL", severity=RiskSeverity.HIGH,
                        subject_id=f"{record.source_file}:{record.source_row}",
                        summary="Record has no structurally usable email identity.",
                        recommended_action="Correct or exclude after manual review.",
                        evidence=record.evidence,
                    ))
            findings.extend(RiskFinding(
                code="DUPLICATE_IDENTITY", severity=RiskSeverity.HIGH,
                subject_id=decision.subject_id,
                summary="Multiple contact rows share an exact normalized email.",
                recommended_action="Review and approve any merge before preparation.",
                evidence=decision.evidence,
            ) for decision in item.duplicate_decisions)
            findings.extend(RiskFinding(
                code="ENTITLEMENT_REVIEW_REQUIRED", severity=RiskSeverity.CRITICAL,
                subject_id=decision.subject_id, summary=decision.rationale,
                recommended_action="Resolve evidence and obtain approval before activation.",
                evidence=decision.evidence,
            ) for decision in item.entitlement_decisions
              if decision.status is not DecisionStatus.VERIFIED)
        return findings

