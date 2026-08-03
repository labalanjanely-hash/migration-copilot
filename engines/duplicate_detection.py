from collections.abc import Sequence

from engines.base import Engine
from models.decisions import Decision, DecisionStatus
from models.migration import NormalizedRecord


class DuplicateDetectionEngine(Engine[NormalizedRecord, list[Decision]]):
    def __init__(self, identity_record_types: tuple[str, ...] = ("contacts",)) -> None:
        self._types = frozenset(identity_record_types)

    def execute(self, items: Sequence[NormalizedRecord]) -> list[Decision]:
        groups: dict[str, list[NormalizedRecord]] = {}
        for record in items:
            if record.record_type in self._types and record.normalized_email:
                groups.setdefault(record.normalized_email, []).append(record)
        return [Decision(
            subject_id=email, decision_type="duplicate_identity_candidate",
            status=DecisionStatus.MANUAL_REVIEW,
            rationale="Multiple source rows share one normalized email; no merge performed.",
            evidence=tuple(ev for row in rows for ev in row.evidence),
            conflicts=(f"{len(rows)} rows share normalized email",),
        ) for email, rows in sorted(groups.items()) if len(rows) > 1]

