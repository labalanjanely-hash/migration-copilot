from dataclasses import dataclass
from pathlib import Path

from openai import APIConnectionError, RateLimitError
from pydantic import BaseModel, ConfigDict, Field

from agents import Agent, Runner, function_tool
from app.inventory import AssetInventoryRepository
from app.storage import SQLiteAuditRepository


class AdvisorUnavailableError(RuntimeError):
    pass


class AdvisoryReport(BaseModel):
    model_config = ConfigDict(frozen=True)
    release_status: str
    executive_summary: str = Field(min_length=1)
    priority_actions: tuple[str, ...]
    evidence_references: tuple[str, ...]
    unresolved_exceptions: tuple[str, ...]
    control_gates: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MigrationAdvisorConfig:
    model: str
    database_path: Path
    instructions_path: Path = Path("docs/agent_prompt.md")
    inventory_path: Path = Path("docs/kajabi-asset-inventory-2026-08-04.json")


class MigrationAdvisor:
    def __init__(self, config: MigrationAdvisorConfig) -> None:
        self._config = config

    def build(self) -> Agent[None]:
        repository = SQLiteAuditRepository(self._config.database_path)
        inventory_repository = AssetInventoryRepository(self._config.inventory_path)

        @function_tool
        def get_migration_run(run_id: str) -> dict[str, object]:
            """Get summarized saved-run evidence by exact run ID."""
            result = repository.get(run_id)
            if result is None:
                return {"found": False, "run_id": run_id}
            return {
                "found": True,
                "run_id": result.run_id,
                "release_status": result.release_status,
                "counts": {
                    "records": len(result.normalized_records),
                    "duplicates": len(result.duplicate_decisions),
                    "entitlements": len(result.entitlement_decisions),
                    "risks": len(result.risks),
                    "entitlement_candidates": len(result.prepared_dataset.rows),
                    "contact_candidates": len(result.prepared_dataset.contact_rows),
                    "manual_review": len(result.prepared_dataset.manual_review_rows),
                },
                "risks": [
                    {
                        "severity": risk.severity.value,
                        "code": risk.code,
                        "subject": risk.subject_id,
                        "summary": risk.summary,
                        "action": risk.recommended_action,
                        "evidence": [
                            f"{x.source_file}:{x.source_row}:{x.source_field}"
                            for x in risk.evidence
                        ],
                    }
                    for risk in result.risks
                ],
            }

        @function_tool
        def get_asset_inventory(section: str = "all") -> dict[str, object]:
            """Get sanitized Kajabi inventory evidence for an exact section or all sections."""
            inventory = inventory_repository.get()
            allowed = {
                "all",
                "live_deltas",
                "products",
                "billing",
                "assets",
                "integrations",
                "gates",
            }
            if section not in allowed:
                return {"found": False, "section": section, "allowed_sections": sorted(allowed)}
            evidence = inventory.section(section)
            return {
                "found": True,
                "snapshot_date": inventory.snapshot_date.isoformat(),
                "source_title": inventory.title,
                "source_url": inventory.source_url,
                "release_status": inventory.release_status,
                "baseline": inventory.baseline,
                "section": section,
                "evidence": [item.model_dump(mode="json") for item in evidence],
            }

        return Agent(
            name="Migration Copilot",
            instructions=self._config.instructions_path.read_text(encoding="utf-8"),
            model=self._config.model,
            tools=[get_migration_run, get_asset_inventory],
            output_type=AdvisoryReport,
        )

    async def advise(self, run_id: str) -> AdvisoryReport:
        try:
            result = await Runner.run(
                self.build(),
                f"Review saved run {run_id}. Use both tools, preserve NO_GO, and cite evidence.",
                max_turns=6,
            )
        except RateLimitError as exc:
            if getattr(exc, "code", None) == "insufficient_quota":
                raise AdvisorUnavailableError(
                    "OpenAI advisory unavailable: API project quota or credits are exhausted."
                ) from exc
            raise AdvisorUnavailableError("OpenAI advisory rate limit reached.") from exc
        except APIConnectionError as exc:
            raise AdvisorUnavailableError("Could not connect to the OpenAI API.") from exc
        return AdvisoryReport.model_validate(result.final_output)
