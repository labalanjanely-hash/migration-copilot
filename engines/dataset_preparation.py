from collections.abc import Sequence

from engines.base import Engine
from models.decisions import Decision, DecisionStatus
from models.migration import PreparedDataset


class DatasetPreparationEngine(Engine[Decision, PreparedDataset]):
    def execute(self, items: Sequence[Decision]) -> PreparedDataset:
        rows: list[dict[str, object]] = []
        excluded: list[Decision] = []
        for decision in items:
            email, separator, key = decision.subject_id.partition("|")
            if (
                decision.status is not DecisionStatus.VERIFIED
                or not separator
                or not email
                or not key
            ):
                excluded.append(decision)
                continue
            rows.append({
                "Email": email,
                "Entitlement Key": key,
                "Decision Status": decision.status.value,
                "Evidence Count": len(decision.evidence),
                "Activation Authorized": False,
            })
        return PreparedDataset(rows=tuple(rows), excluded_decisions=tuple(excluded))
