from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class InventoryEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    classification: str
    subject: str
    observation: str
    treatment: str


class AssetInventory(BaseModel):
    model_config = ConfigDict(frozen=True)

    snapshot_date: date
    title: str
    source_url: str
    release_status: str = "NO_GO"
    baseline: dict[str, str]
    sections: dict[str, tuple[InventoryEvidence, ...]] = Field(default_factory=dict)

    def section(self, name: str) -> tuple[InventoryEvidence, ...]:
        if name == "all":
            return tuple(item for items in self.sections.values() for item in items)
        return self.sections.get(name, ())
