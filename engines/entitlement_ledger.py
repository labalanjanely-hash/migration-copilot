from collections.abc import Sequence

from engines.base import Engine
from models.decisions import Decision, DecisionStatus
from models.migration import NormalizedRecord
from rules.configuration import PipelineConfiguration


class EntitlementLedgerEngine(Engine[NormalizedRecord, list[Decision]]):
    def __init__(self, configuration: PipelineConfiguration) -> None:
        self._config = configuration

    def execute(self, items: Sequence[NormalizedRecord]) -> list[Decision]:
        groups: dict[tuple[str, str], list[tuple[NormalizedRecord, str | None]]] = {}
        access_only: list[Decision] = []
        rules = self._config.entitlement
        for record in items:
            mapping = self._config.fields_by_record_type[record.record_type]
            key = self._key(record, mapping.offer_id, mapping.product_id)
            if not record.normalized_email or not key:
                continue
            subject = f"{record.normalized_email}|{key}"
            if record.record_type in rules.access_record_types:
                access_only.append(Decision(
                    subject_id=subject, decision_type="entitlement",
                    status=DecisionStatus.MANUAL_REVIEW,
                    rationale="Product access is current-access evidence, not purchase evidence.",
                    evidence=record.evidence,
                ))
                continue
            if record.record_type not in (
                *rules.purchase_record_types, *rules.negative_record_types
            ):
                continue
            status = self._field(record, mapping.status)
            if record.record_type in rules.negative_record_types:
                status = record.record_type.removesuffix("s")
            groups.setdefault((record.normalized_email, key), []).append(
                (record, status.casefold() if status else None)
            )
        decisions: list[Decision] = []
        for (email, key), entries in sorted(groups.items()):
            statuses = {status for _, status in entries if status}
            evidence = tuple(ev for record, _ in entries for ev in record.evidence)
            succeeded = bool(statuses.intersection(rules.succeeded_statuses))
            conflicts = statuses.intersection(rules.conflicting_statuses).union(
                statuses.intersection({"refund", "dispute"})
            )
            if succeeded and not conflicts:
                decisions.append(Decision(
                    subject_id=f"{email}|{key}", decision_type="entitlement",
                    status=DecisionStatus.VERIFIED,
                    rationale="Succeeded purchase evidence matched an explicit entitlement key.",
                    evidence=evidence,
                ))
            else:
                decisions.append(Decision(
                    subject_id=f"{email}|{key}", decision_type="entitlement",
                    status=DecisionStatus.MANUAL_REVIEW,
                    rationale="Purchase evidence is insufficient or conflicting.",
                    evidence=evidence,
                    conflicts=tuple(sorted(conflicts)) or ("no succeeded purchase status",),
                ))
        decided = {item.subject_id for item in decisions}
        decisions.extend(item for item in access_only if item.subject_id not in decided)
        return decisions

    @staticmethod
    def _field(record: NormalizedRecord, field: str | None) -> str | None:
        value = record.values.get(field) if field else None
        text = str(value).strip() if value is not None else ""
        return text or None

    def _key(self, record: NormalizedRecord, offer: str | None, product: str | None) -> str | None:
        offer_id = self._field(record, offer)
        if offer_id:
            return f"offer:{offer_id}"
        product_id = self._field(record, product)
        return f"product:{product_id}" if product_id else None
