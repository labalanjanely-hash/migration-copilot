from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceFieldMap(BaseModel):
    model_config = ConfigDict(frozen=True)
    email: str = Field(min_length=1)
    name: str | None = None
    phone: str | None = None
    status: str | None = None
    offer_id: str | None = None
    product_id: str | None = None
    transaction_id: str | None = None


class EntitlementRules(BaseModel):
    model_config = ConfigDict(frozen=True)
    purchase_record_types: tuple[str, ...] = ("transactions", "offer_purchases")
    access_record_types: tuple[str, ...] = ("product_access",)
    negative_record_types: tuple[str, ...] = ("refunds", "disputes")
    succeeded_statuses: tuple[str, ...] = ("succeeded", "paid")
    conflicting_statuses: tuple[str, ...] = (
        "failed", "refunded", "disputed", "canceled", "cancelled", "paused",
        "past_due", "pending_cancellation", "trialing",
    )


class PipelineConfiguration(BaseModel):
    model_config = ConfigDict(frozen=True)
    version: str
    fields_by_record_type: dict[str, SourceFieldMap]
    identity_record_types: tuple[str, ...] = ("contacts",)
    entitlement: EntitlementRules = EntitlementRules()

    @model_validator(mode="after")
    def require_mapping(self) -> "PipelineConfiguration":
        if not self.fields_by_record_type:
            raise ValueError("At least one explicit field mapping is required.")
        return self
