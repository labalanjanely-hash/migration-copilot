from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvidenceType(StrEnum):
    SOURCE_RECORD = "source_record"
    CONTACT = "contact"
    TRANSACTION = "transaction"
    SUBSCRIPTION = "subscription"
    PAYMENT_PLAN = "payment_plan"
    OFFER_PURCHASE = "offer_purchase"
    PRODUCT_ACCESS = "product_access"
    COMMUNITY_MEMBERSHIP = "community_membership"
    REFUND = "refund"
    DISPUTE = "dispute"


class Evidence(BaseModel):
    model_config = ConfigDict(frozen=True)
    evidence_type: EvidenceType
    source_file: str = Field(min_length=1)
    source_row: int = Field(ge=1)
    source_field: str = Field(min_length=1)
    raw_value: Any
    checksum: str | None = None

