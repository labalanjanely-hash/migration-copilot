import re
from collections.abc import Sequence

from engines.base import Engine
from models.evidence import Evidence, EvidenceType
from models.migration import NormalizedRecord
from models.records import SourceRecord
from rules.configuration import PipelineConfiguration


class NormalizationEngine(Engine[SourceRecord, list[NormalizedRecord]]):
    def __init__(self, configuration: PipelineConfiguration) -> None:
        self._config = configuration

    def execute(self, items: Sequence[SourceRecord]) -> list[NormalizedRecord]:
        return [self._normalize(item) for item in items]

    def _normalize(self, record: SourceRecord) -> NormalizedRecord:
        mapping = self._config.fields_by_record_type.get(record.record_type)
        if mapping is None:
            raise ValueError(f"No field mapping for record type: {record.record_type}")
        fields = tuple(value for value in mapping.model_dump().values() if isinstance(value, str))
        evidence = tuple(Evidence(
            evidence_type=self._evidence_type(record.record_type),
            source_file=record.source_file, source_row=record.source_row,
            source_field=field, raw_value=record.values.get(field),
        ) for field in fields if field in record.values) or (Evidence(
            evidence_type=EvidenceType.SOURCE_RECORD, source_file=record.source_file,
            source_row=record.source_row, source_field="__row__", raw_value="present",
        ),)
        phone_raw = record.values.get(mapping.phone) if mapping.phone else None
        digits = re.sub(r"\D", "", str(phone_raw)) if phone_raw else ""
        return NormalizedRecord(
            source_file=record.source_file, source_row=record.source_row,
            record_type=record.record_type,
            normalized_email=self._text(record.values.get(mapping.email), casefold=True),
            normalized_phone=("+" if str(phone_raw).strip().startswith("+") else "") + digits
            if digits else None,
            normalized_name=self._text(record.values.get(mapping.name) if mapping.name else None),
            values=record.values, evidence=evidence,
        )

    @staticmethod
    def _text(value: object, casefold: bool = False) -> str | None:
        text = " ".join(str(value).split()) if value is not None else ""
        return (text.casefold() if casefold else text) or None

    @staticmethod
    def _evidence_type(record_type: str) -> EvidenceType:
        aliases = {
            "contacts": EvidenceType.CONTACT, "transactions": EvidenceType.TRANSACTION,
            "subscriptions": EvidenceType.SUBSCRIPTION,
            "payment_plans": EvidenceType.PAYMENT_PLAN,
            "offer_purchases": EvidenceType.OFFER_PURCHASE,
            "product_access": EvidenceType.PRODUCT_ACCESS,
            "community_memberships": EvidenceType.COMMUNITY_MEMBERSHIP,
            "refunds": EvidenceType.REFUND, "disputes": EvidenceType.DISPUTE,
        }
        return aliases.get(record_type, EvidenceType.SOURCE_RECORD)

