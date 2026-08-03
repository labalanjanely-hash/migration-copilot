from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from models.evidence import Evidence


class DecisionStatus(StrEnum):
    VERIFIED = "verified"
    PROPOSED = "proposed"
    MANUAL_REVIEW = "manual_review"
    HOLD = "hold"
    NOT_READY = "not_ready"


class Decision(BaseModel):
    model_config = ConfigDict(frozen=True)
    subject_id: str = Field(min_length=1)
    decision_type: str = Field(min_length=1)
    status: DecisionStatus
    rationale: str = Field(min_length=1)
    evidence: tuple[Evidence, ...] = Field(min_length=1)
    conflicts: tuple[str, ...] = ()

    @model_validator(mode="after")
    def conflicts_require_review(self) -> "Decision":
        if self.conflicts and self.status is not DecisionStatus.MANUAL_REVIEW:
            raise ValueError("Conflicting evidence requires manual_review status.")
        return self

