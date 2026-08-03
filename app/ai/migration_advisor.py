from dataclasses import dataclass
from pathlib import Path

from openai import APIConnectionError, RateLimitError
from pydantic import BaseModel, ConfigDict, Field

from agents import Agent, Runner, function_tool
from app.storage import SQLiteAuditRepository


class AdvisorUnavailableError(RuntimeError):
    pass


class AdvisoryReport(BaseModel):
    model_config = ConfigDict(frozen=True)
    release_status: str
    executive_summary: str = Field(min_length=1)
    priority_actions: tuple[str, ...]
    evidence_references: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MigrationAdvisorConfig:
    model: str
    database_path: Path
    instructions_path: Path = Path("docs/agent_prompt.md")


class MigrationAdvisor:
    def __init__(self, config: MigrationAdvisorConfig) -> None:
        self._config = config

    def build(self) -> Agent[None]:
        repository = SQLiteAuditRepository(self._config.database_path)

        @function_tool
        def get_migration_run(run_id: str) -> dict[str, object]:
            """Get summarized saved-run evidence by exact run ID."""
            result = repository.get(run_id)
            if result is None:
                return {"found": False, "run_id": run_id}
            return {
                "found": True, "run_id": result.run_id,
                "release_status": result.release_status,
                "counts": {"records": len(result.normalized_records),
                           "duplicates": len(result.duplicate_decisions),
                           "entitlements": len(result.entitlement_decisions),
                           "risks": len(result.risks),
                           "candidates": len(result.prepared_dataset.rows)},
                "risks": [{
                    "severity": risk.severity.value, "code": risk.code,
                    "subject": risk.subject_id, "summary": risk.summary,
                    "action": risk.recommended_action,
                    "evidence": [f"{x.source_file}:{x.source_row}:{x.source_field}"
                                 for x in risk.evidence],
                } for risk in result.risks],
            }

        return Agent(
            name="Migration Copilot",
            instructions=self._config.instructions_path.read_text(encoding="utf-8"),
            model=self._config.model,
            tools=[get_migration_run],
            output_type=AdvisoryReport,
        )

    async def advise(self, run_id: str) -> AdvisoryReport:
        try:
            result = await Runner.run(
                self.build(),
                f"Review saved run {run_id}. Use the tool, preserve NO_GO, and cite evidence.",
                max_turns=4,
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

